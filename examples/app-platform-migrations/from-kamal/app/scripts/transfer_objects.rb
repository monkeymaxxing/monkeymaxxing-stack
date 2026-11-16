# Run with the selected source or destination's protected app environment.
require_relative '../config/environment'
require_relative '../lib/object_storage'
require 'json'
require 'fileutils'
root = ENV.fetch('EXPORT_DIR')
command = ARGV.fetch(0)
client = ObjectStorage.client
bucket = ENV.fetch('R2_BUCKET')
if command == 'export'
  Dir.mkdir(root, 0700)
  manifest = []
  token = nil
  loop do
    result = client.list_objects_v2(bucket: bucket, continuation_token: token)
    result.contents.each do |object|
      bytes = client.get_object(bucket: bucket, key: object.key).body.read
      digest = Digest::SHA256.hexdigest(bytes)
      File.write(File.join(root, digest), bytes, mode: 'wb', perm: 0600)
      manifest << {key: object.key, sha256: digest, bytes: bytes.bytesize}
    end
    break unless result.is_truncated
    token = result.next_continuation_token
  end
  Document.find_each do |document|
    raise 'document missing from export' unless manifest.any? { |entry| entry[:key] == document.object_key && entry[:sha256] == document.sha256 }
  end
  File.write(File.join(root, 'manifest.json'), JSON.generate(manifest), perm: 0600)
elsif command == 'import'
  manifest = JSON.parse(File.read(File.join(root, 'manifest.json')), symbolize_names: true)
  # Use a new, empty bucket. This check also catches an accidentally selected source.
  raise 'destination bucket must be empty' unless client.list_objects_v2(bucket: bucket, max_keys: 1).contents.empty?
  manifest.each do |entry|
    bytes = File.binread(File.join(root, entry.fetch(:sha256)))
    raise 'export bytes changed' unless bytes.bytesize == entry.fetch(:bytes) && Digest::SHA256.hexdigest(bytes) == entry.fetch(:sha256)
    client.put_object(bucket: bucket, key: entry.fetch(:key), body: bytes, if_none_match: '*')
    saved = client.get_object(bucket: bucket, key: entry.fetch(:key)).body.read
    raise 'import bytes differ' unless saved == bytes
  end
else
  abort 'usage: bundle exec ruby scripts/transfer_objects.rb export|import'
end
puts "PASS: #{command} #{manifest.length} private objects"

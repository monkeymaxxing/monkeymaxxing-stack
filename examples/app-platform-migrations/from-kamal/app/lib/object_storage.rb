require "digest"
require "securerandom"
module ObjectStorage
  # Bound memory and transfer duration for this small-file example.
  MAX_BYTES = 8 * 1024 * 1024
  def self.client
    Aws::S3::Client.new(endpoint: ENV.fetch("R2_ENDPOINT"), region: "auto",
      credentials: Aws::Credentials.new(ENV.fetch("R2_ACCESS_KEY_ID"), ENV.fetch("R2_SECRET_ACCESS_KEY")),
      force_path_style: true, retry_limit: 0, http_open_timeout: 3, http_read_timeout: 12)
  end
  def self.upload(account, filename, bytes)
    raise ArgumentError, "file exceeds 8 MiB" if bytes.bytesize > MAX_BYTES
    key = "documents/#{account.id}/#{SecureRandom.uuid}"
    client.put_object(bucket: ENV.fetch("R2_BUCKET"), key: key, body: bytes, content_type: "application/octet-stream")
    # A failed metadata commit may leave an orphan object. Never delete an object
    # after an uncertain commit: its row may have been saved. Reconcile by key.
    Document.create!(account: account, filename: filename, object_key: key, sha256: Digest::SHA256.hexdigest(bytes))
  end
  def self.download(document)
    bytes = client.get_object(bucket: ENV.fetch("R2_BUCKET"), key: document.object_key).body.read
    raise IOError, "document checksum mismatch" unless Digest::SHA256.hexdigest(bytes) == document.sha256
    bytes
  end
end

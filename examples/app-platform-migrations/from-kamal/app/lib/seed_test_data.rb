require_relative "object_storage"
module SeedTestData
  def self.run(arguments = [])
    raise "seed-test-data refuses to run: APP_ENV must be development or staging, so production never gets test data" unless ["development", "staging"].include?(ENV["APP_ENV"])
    usage = "Usage: seed-test-data [--accounts N], where N is a whole number of at least 2"
    count = 2
    unless arguments.empty?
      raise usage unless arguments.length == 2 && arguments[0] == "--accounts" && /\A[0-9]+\z/.match?(arguments[1])
      count = Integer(arguments[1], 10)
      raise usage if count < 2
    end
    password = ENV.fetch("FIXTURE_PASSWORD")
    raise "FIXTURE_PASSWORD must be 12 to 72 bytes" unless (12..72).cover?(password.bytesize)
    [["barbara", "Barbara", "First"], ["michael", "Michael", "Second"]].each do |slug, name, ordinal|
      account = Account.find_or_create_by!(email: "#{slug}@example.com") { |row| row.password = password }
      Record.find_or_create_by!(account: account, title: "#{name} invoice") { |row| row.description = "#{ordinal} synthetic record" }
      unless Document.exists?(account: account, filename: "#{slug}-note.txt")
        ObjectStorage.upload(account, "#{slug}-note.txt", "#{name} synthetic document\n")
      end
      ReportJob.create!(account: account) unless ReportJob.exists?(account: account)
    end
    password_hash = BCrypt::Password.create(password).to_s
    Account.transaction do
      connection = Account.connection
      connection.execute("SELECT pg_advisory_xact_lock(20261105)")
      connection.execute(<<~SQL)
        INSERT INTO accounts(email,password_digest)
        SELECT 'test-account-' || repeat('0',greatest(0,6-length(n::text))) || n::text || '@example.com',#{connection.quote(password_hash)}
        FROM generate_series(3,#{count}::bigint) AS n ON CONFLICT(email) DO NOTHING
      SQL
      connection.execute(<<~SQL)
        INSERT INTO records(account_id,title,description)
        SELECT a.id,'Test record ' || n::text,'Generated test record'
        FROM generate_series(3,#{count}::bigint) AS n
        JOIN accounts a ON a.email='test-account-' || repeat('0',greatest(0,6-length(n::text))) || n::text || '@example.com'
        WHERE NOT EXISTS(SELECT 1 FROM records r WHERE r.account_id=a.id)
      SQL
    end
    puts "synthetic test fixture ready"
  end
end

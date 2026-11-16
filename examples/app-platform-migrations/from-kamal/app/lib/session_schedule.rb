module SessionSchedule
  # One UTC occurrence per day. Starting after a missed day runs today's task.
  # The row and deletions commit together, including during scheduler overlap.
  def self.tick
    connection = ActiveRecord::Base.connection
    connection.transaction do
      connection.execute("SET LOCAL statement_timeout = '12s'")
      connection.execute("SET LOCAL lock_timeout = '5s'")
      claimed = connection.exec_query(<<~SQL)
        INSERT INTO schedule_runs (utc_date, removed_sessions)
        VALUES ((CURRENT_TIMESTAMP AT TIME ZONE 'UTC')::date, 0)
        ON CONFLICT (utc_date) DO NOTHING RETURNING id
      SQL
      unless claimed.empty?
        removed = connection.exec_delete("DELETE FROM login_sessions WHERE expires_at < CURRENT_TIMESTAMP")
        connection.execute("UPDATE schedule_runs SET removed_sessions = #{Integer(removed)} WHERE id = #{Integer(claimed.first.fetch('id'))}")
      end
    end
  end

  def self.run
    stopping = false
    %w[TERM INT].each { |signal| Signal.trap(signal) { stopping = true } }
    until stopping
      tick
      sleep 1 unless stopping
    end
  end
end

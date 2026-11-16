module ReportWorker
  def self.run
    stopping = false
    %w[TERM INT].each { |signal| Signal.trap(signal) { stopping = true } }
    until stopping
      begin
        worked = ReportJob.transaction do
          ReportJob.connection.execute("SET LOCAL statement_timeout = '12s'")
          ReportJob.connection.execute("SET LOCAL lock_timeout = '5s'")
          job = ReportJob.where(completed_at: nil).order(:id).lock("FOR UPDATE SKIP LOCKED").first
          if job
            count = Record.where(account_id: job.account_id).count
            job.update!(output: "record_count=#{count}\n", completed_at: Time.current)
            true
          end
        end
      rescue ActiveRecord::ActiveRecordError, PG::Error
        ActiveRecord::Base.connection_pool.disconnect!
        warn "report transaction failed; pending work remains available"
        worked = false
      end
      sleep 0.25 unless worked || stopping
    end
  end
end

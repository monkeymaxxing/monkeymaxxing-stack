class CreateScheduleRuns < ActiveRecord::Migration[8.1]
  def change
    create_table :schedule_runs do |t|
      t.date :utc_date, null: false
      t.integer :removed_sessions, null: false
    end
    add_index :schedule_runs, :utc_date, unique: true
  end
end

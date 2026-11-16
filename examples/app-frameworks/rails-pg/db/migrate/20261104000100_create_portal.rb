class CreatePortal < ActiveRecord::Migration[8.1]
  def change
    create_table :accounts do |t|
      t.string :email, null: false
      t.string :password_digest, null: false
    end
    add_index :accounts, :email, unique: true
    create_table :login_sessions do |t|
      t.references :account, null: false, foreign_key: true
      t.string :token_hash, null: false
      t.datetime :expires_at, null: false
    end
    add_index :login_sessions, :token_hash, unique: true
    create_table :records do |t|
      t.references :account, null: false, foreign_key: true
      t.string :title, null: false
    end
    create_table :documents do |t|
      t.references :account, null: false, foreign_key: true
      t.string :filename, null: false
      t.string :object_key, null: false
      t.string :sha256, null: false
    end
    add_index :documents, [:account_id, :filename], unique: true
    create_table :report_jobs do |t|
      t.references :account, null: false, foreign_key: true
      t.text :output
      t.datetime :completed_at
    end
    add_index :report_jobs, :id, where: "completed_at IS NULL", name: "waiting_reports"
  end
end

class AddRecordDescriptions < ActiveRecord::Migration[8.1]
  def change
    add_column :records, :description, :text, null: false, default: ""
  end
end

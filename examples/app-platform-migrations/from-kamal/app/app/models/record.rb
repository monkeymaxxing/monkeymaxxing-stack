class Record < ApplicationRecord
  belongs_to :account
  validates :title, presence: true, length: { maximum: 200 }
  validates :description, length: { maximum: 10000 }
end

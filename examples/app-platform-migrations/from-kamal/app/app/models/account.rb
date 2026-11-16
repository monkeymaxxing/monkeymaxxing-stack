class Account < ApplicationRecord
  has_secure_password
  validates :email, presence: true, uniqueness: true, format: { with: /\A[^\s@]+@[^\s@]+\.[^\s@]+\z/ }
  validate do
    if password && !(12..72).cover?(password.bytesize)
      errors.add(:password, "must be 12 to 72 bytes")
    end
  end
end

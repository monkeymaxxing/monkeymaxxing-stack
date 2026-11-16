require "digest"
require "securerandom"
require_relative "../../lib/object_storage"
class PortalController < ActionController::Base
  layout "application"
  # Exact Origin on every mutation replaces token-based CSRF for this same-origin API.
  skip_forgery_protection
  around_action :with_database_timeouts
  before_action :headers_and_origin
  before_action :authenticate, except: [:home, :health, :register, :login]
  rescue_from ActiveRecord::ActiveRecordError, PG::Error, with: :database_error
  rescue_from ActiveRecord::RecordInvalid do
    render json: { error: "invalid or duplicate values" }, status: 422
  end
  rescue_from ActiveRecord::RecordNotFound do
    render json: { error: "not found" }, status: 404
  end
  rescue_from Aws::Errors::ServiceError, Seahorse::Client::NetworkingError, IOError do
    render json: { error: "document storage unavailable" }, status: 503
  end
  def with_database_timeouts
    ActiveRecord::Base.transaction do
      ActiveRecord::Base.connection.execute("SET LOCAL statement_timeout = '12s'")
      ActiveRecord::Base.connection.execute("SET LOCAL lock_timeout = '5s'")
      yield
    end
  end
  def home; render :home; end
  def health
    ActiveRecord::Base.connection_pool.with_connection { |connection| connection.execute("SELECT 1") }
    render json: { status: "ok" }
  end
  def register
    account = Account.create!(email: params[:email].to_s.strip.downcase, password: params[:password].to_s)
    issue_session(account)
  end
  def login
    account = Account.find_by(email: params[:email].to_s.strip.downcase)
    if account&.authenticate(params[:password].to_s)
      issue_session(account)
    else
      render json: { error: "invalid login" }, status: 401
    end
  end
  def logout
    LoginSession.where(token_hash: Digest::SHA256.hexdigest(cookies[:portal_session].to_s)).delete_all
    cookies.delete(:portal_session, secure: true, httponly: true, same_site: :lax, path: "/")
    render json: { status: "logged out" }
  end
  def records
    render json: Record.where(account: @account).order(:id).as_json(only: [:id, :title, :description])
  end
  def create_record
    row = Record.create!(account: @account, title: params[:title], description: params[:description].to_s)
    render json: { id: row.id }, status: 201
  end
  def update_record
    row = owned_record
    row.update!(title: params[:title], description: params[:description].to_s)
    render json: { status: "updated" }
  end
  def delete_record
    owned_record.destroy!
    render json: { status: "deleted" }
  end
  def documents
    render json: Document.where(account: @account).order(:id).as_json(only: [:id, :filename, :sha256])
  end
  def upload
    file = params[:file]
    unless file.respond_to?(:size) && file.size <= ObjectStorage::MAX_BYTES
      render json: { error: "choose a file of at most 8 MiB" }, status: 422
      return
    end
    row = ObjectStorage.upload(@account, File.basename(file.original_filename), file.read)
    render json: { id: row.id }, status: 201
  end
  def download
    row = Document.find_by!(id: params[:id], account: @account)
    send_data ObjectStorage.download(row), type: "application/octet-stream", disposition: "attachment", filename: row.filename
  end
  def reports
    render json: ReportJob.where(account: @account).order(:id).as_json(only: [:id, :output])
  end
  def report
    render json: ReportJob.find_by!(id: params[:id], account: @account).as_json(only: [:id, :output])
  end
  def queue_report
    render json: { id: ReportJob.create!(account: @account).id }, status: 201
  end
  private
  def headers_and_origin
    response.headers["Cache-Control"] = "no-store"
    response.headers["X-Content-Type-Options"] = "nosniff"
    response.headers["Content-Security-Policy"] = "default-src 'self'; script-src 'self' 'unsafe-inline'; style-src 'self'; base-uri 'none'; frame-ancestors 'none'"
    unless request.get? || request.head? || request.headers["Origin"] == ENV.fetch("APP_ORIGIN")
      render json: { error: "origin refused" }, status: 403
    end
  end
  def authenticate
    token = Digest::SHA256.hexdigest(cookies[:portal_session].to_s)
    session = LoginSession.where(token_hash: token).where("expires_at > ?", Time.current).first
    if session
      @account = session.account
    else
      render json: { error: "login required" }, status: 401
    end
  end
  def issue_session(account)
    token = SecureRandom.hex(32)
    LoginSession.create!(account: account, token_hash: Digest::SHA256.hexdigest(token), expires_at: 7.days.from_now)
    cookies[:portal_session] = { value: token, secure: true, httponly: true, same_site: :lax, path: "/", expires: 7.days.from_now }
    render json: { status: "logged in" }
  end
  def owned_record
    Record.find_by!(id: params[:id], account: @account)
  end
  def database_error
    # Never retry a request: its transaction may already have committed.
    ActiveRecord::Base.connection_pool.disconnect!
    render json: { error: "database unavailable; check saved data before retrying" }, status: 503
  end
end

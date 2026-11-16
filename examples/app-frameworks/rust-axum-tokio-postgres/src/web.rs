use crate::{Database, database::LATEST_MIGRATION, storage};
use askama::Template;
use axum::{
    Form, Json, Router,
    extract::{DefaultBodyLimit, Multipart, Path, Request, State},
    http::{HeaderMap, StatusCode, header},
    middleware::{self, Next},
    response::{Html, IntoResponse, Redirect, Response},
    routing::{get, post},
};
use rand::RngCore;
use s3::Bucket;
use serde::{Deserialize, Serialize};
use serde_json::json;
use std::{sync::Arc, time::Duration};

pub struct App {
    pub database: Database,
    pub bucket: Box<Bucket>,
    pub origin: String,
}
type Result<T> = std::result::Result<T, StatusCode>;
fn unavailable<E>(_: E) -> StatusCode {
    StatusCode::SERVICE_UNAVAILABLE
}
#[derive(Serialize)]
struct Record {
    id: i64,
    title: String,
    description: String,
}
#[derive(Template)]
#[template(path = "portal.html")]
struct PortalPage {
    records: Vec<Record>,
    documents: Vec<Document>,
    reports: Vec<Report>,
}
struct Document {
    id: i64,
    file_name: String,
}
struct Report {
    id: i64,
    output: String,
}
#[derive(Template)]
#[template(path = "landing.html")]
struct LandingPage;

pub fn routes(app: Arc<App>) -> Router {
    Router::new()
        .route("/", get(home))
        .route("/healthz", get(health))
        .route("/register", post(register))
        .route("/login", post(login))
        .route("/logout", post(logout))
        .route("/records", get(records).post(create_record))
        .route("/records/{id}/update", post(update_record))
        .route("/records/{id}/delete", post(delete_record))
        .route("/documents", get(documents).post(upload))
        .route("/documents/{id}", get(download))
        .route("/reports", get(reports).post(queue_report))
        .layer(DefaultBodyLimit::max(storage::MAX_UPLOAD_BYTES + 64 * 1024))
        .layer(middleware::from_fn_with_state(app.clone(), security))
        .with_state(app)
}
async fn security(State(app): State<Arc<App>>, request: Request, next: Next) -> Response {
    let timeout = if request.uri().path() == "/healthz" {
        2
    } else {
        12
    };
    let method = request.method().as_str();
    let mut response = if method != "GET"
        && method != "HEAD"
        && request
            .headers()
            .get(header::ORIGIN)
            .and_then(|v| v.to_str().ok())
            != Some(app.origin.as_str())
    {
        StatusCode::FORBIDDEN.into_response()
    } else {
        match tokio::time::timeout(Duration::from_secs(timeout), next.run(request)).await {
            Ok(response) => response,
            Err(_) => StatusCode::SERVICE_UNAVAILABLE.into_response(),
        }
    };
    response
        .headers_mut()
        .insert("x-content-type-options", "nosniff".parse().unwrap());
    response
        .headers_mut()
        .insert(header::CACHE_CONTROL, "no-store".parse().unwrap());
    response.headers_mut().insert(
        "content-security-policy",
        "default-src 'none'; form-action 'self'; frame-ancestors 'none'; base-uri 'none'"
            .parse()
            .unwrap(),
    );
    response
}
fn token() -> String {
    let mut bytes = [0u8; 32];
    rand::rngs::OsRng.fill_bytes(&mut bytes);
    hex::encode(bytes)
}
fn cookie(headers: &HeaderMap) -> Option<String> {
    headers
        .get_all(header::COOKIE)
        .iter()
        .filter_map(|v| v.to_str().ok())
        .flat_map(|v| v.split(';'))
        .find_map(|part| {
            part.trim()
                .strip_prefix("__Host-portal_session=")
                .map(String::from)
        })
}
fn response(headers: &HeaderMap, value: serde_json::Value, status: StatusCode) -> Response {
    if headers
        .get(header::ACCEPT)
        .and_then(|v| v.to_str().ok())
        .is_some_and(|v| v.contains("application/json"))
    {
        (status, Json(value)).into_response()
    } else {
        Redirect::to("/").into_response()
    }
}
async fn owner(app: &App, headers: &HeaderMap) -> Result<i64> {
    let token = cookie(headers).ok_or(StatusCode::UNAUTHORIZED)?;
    let conn = app.database.get().await.map_err(unavailable)?;
    let row = conn
        .query_opt(
            "select account_id from sessions where token_hash=$1 and expires_at>now()",
            &[&storage::digest(token.as_bytes())],
        )
        .await
        .map_err(unavailable)?;
    Ok(row.ok_or(StatusCode::UNAUTHORIZED)?.get(0))
}
async fn health(State(app): State<Arc<App>>) -> Result<Json<serde_json::Value>> {
    let conn = app.database.get().await.map_err(unavailable)?;
    let ready: bool = conn
        .query_one(
            "select exists(select 1 from schema_migrations where version=$1)",
            &[&LATEST_MIGRATION],
        )
        .await
        .map_err(unavailable)?
        .get(0);
    if !ready {
        return Err(StatusCode::SERVICE_UNAVAILABLE);
    }
    Ok(Json(
        json!({"status":"ok", "release":option_env!("RELEASE").unwrap_or("development")}),
    ))
}
async fn home(State(app): State<Arc<App>>, headers: HeaderMap) -> Result<Html<String>> {
    if cookie(&headers).is_none() {
        return Ok(Html(LandingPage.render().map_err(unavailable)?));
    }
    let account = owner(&app, &headers).await?;
    let records = record_list(&app, account).await?;
    let conn = app.database.get().await.map_err(unavailable)?;
    let documents = conn
        .query(
            "select id,file_name from documents where account_id=$1 order by id",
            &[&account],
        )
        .await
        .map_err(unavailable)?
        .iter()
        .map(|r| Document {
            id: r.get(0),
            file_name: r.get(1),
        })
        .collect();
    let reports = conn
        .query(
            "select id,output from report_jobs where account_id=$1 order by id",
            &[&account],
        )
        .await
        .map_err(unavailable)?
        .iter()
        .map(|r| Report {
            id: r.get(0),
            output: r
                .get::<_, Option<String>>(1)
                .unwrap_or_else(|| "Waiting for a worker. Refresh to check completion.".into()),
        })
        .collect();
    Ok(Html(
        PortalPage {
            records,
            documents,
            reports,
        }
        .render()
        .map_err(unavailable)?,
    ))
}
#[derive(Deserialize)]
struct Credentials {
    email: String,
    password: String,
}
fn validate_credentials(mut value: Credentials) -> Result<Credentials> {
    value.email = value.email.trim().to_lowercase();
    let parts: Vec<_> = value.email.split('@').collect();
    if !(12..=72).contains(&value.password.len())
        || value.email.len() > 254
        || parts.len() != 2
        || parts.iter().any(|s| s.is_empty())
        || value
            .email
            .chars()
            .any(|c| c.is_whitespace() || c == '<' || c == '>')
    {
        return Err(StatusCode::BAD_REQUEST);
    }
    Ok(value)
}
async fn register(
    State(app): State<Arc<App>>,
    headers: HeaderMap,
    Form(value): Form<Credentials>,
) -> Result<Response> {
    let value = validate_credentials(value)?;
    let hash =
        tokio::task::spawn_blocking(move || bcrypt::hash(value.password, bcrypt::DEFAULT_COST))
            .await
            .map_err(unavailable)?
            .map_err(unavailable)?;
    let conn = app.database.get().await.map_err(unavailable)?;
    let row=conn.query_opt("insert into accounts(email,password_hash) values($1,$2) on conflict(email) do nothing returning id", &[&value.email,&hash]).await.map_err(unavailable)?;
    let account: i64 = row.ok_or(StatusCode::CONFLICT)?.get(0);
    drop(conn);
    new_session(&app, &headers, account).await
}
async fn login(
    State(app): State<Arc<App>>,
    headers: HeaderMap,
    Form(value): Form<Credentials>,
) -> Result<Response> {
    let value = validate_credentials(value).map_err(|_| StatusCode::UNAUTHORIZED)?;
    let conn = app.database.get().await.map_err(unavailable)?;
    let row = conn
        .query_opt(
            "select id,password_hash from accounts where email=$1",
            &[&value.email],
        )
        .await
        .map_err(unavailable)?
        .ok_or(StatusCode::UNAUTHORIZED)?;
    let account: i64 = row.get(0);
    let hash: String = row.get(1);
    drop(conn);
    if !tokio::task::spawn_blocking(move || bcrypt::verify(value.password, &hash))
        .await
        .map_err(unavailable)?
        .map_err(unavailable)?
    {
        return Err(StatusCode::UNAUTHORIZED);
    }
    new_session(&app, &headers, account).await
}
async fn new_session(app: &App, headers: &HeaderMap, account: i64) -> Result<Response> {
    let token = token();
    let mut conn = app.database.get().await.map_err(unavailable)?;
    let tx = conn.transaction().await.map_err(unavailable)?;
    if let Some(old) = cookie(headers) {
        tx.execute(
            "delete from sessions where token_hash=$1",
            &[&storage::digest(old.as_bytes())],
        )
        .await
        .map_err(unavailable)?;
    }
    tx.execute(
        "insert into sessions values($1,$2,now()+interval '7 days')",
        &[&storage::digest(token.as_bytes()), &account],
    )
    .await
    .map_err(unavailable)?;
    tx.commit().await.map_err(unavailable)?;
    let mut result = response(headers, json!({"account_id":account}), StatusCode::OK);
    result.headers_mut().insert(
        header::SET_COOKIE,
        format!(
            "__Host-portal_session={token}; Path=/; Secure; HttpOnly; SameSite=Lax; Max-Age=604800"
        )
        .parse()
        .unwrap(),
    );
    Ok(result)
}
async fn logout(State(app): State<Arc<App>>, headers: HeaderMap) -> Result<Response> {
    if let Some(old) = cookie(&headers) {
        app.database
            .get()
            .await
            .map_err(unavailable)?
            .execute(
                "delete from sessions where token_hash=$1",
                &[&storage::digest(old.as_bytes())],
            )
            .await
            .map_err(unavailable)?;
    }
    let mut result = response(&headers, json!({"logged_out":true}), StatusCode::OK);
    result.headers_mut().insert(
        header::SET_COOKIE,
        "__Host-portal_session=; Path=/; Secure; HttpOnly; SameSite=Lax; Max-Age=0"
            .parse()
            .unwrap(),
    );
    Ok(result)
}
async fn record_list(app: &App, account: i64) -> Result<Vec<Record>> {
    Ok(app
        .database
        .get()
        .await
        .map_err(unavailable)?
        .query(
            "select id,title,description from records where account_id=$1 order by id",
            &[&account],
        )
        .await
        .map_err(unavailable)?
        .iter()
        .map(|r| Record {
            id: r.get(0),
            title: r.get(1),
            description: r.get(2),
        })
        .collect())
}
async fn records(State(app): State<Arc<App>>, headers: HeaderMap) -> Result<Response> {
    let account = owner(&app, &headers).await?;
    Ok(response(
        &headers,
        json!(record_list(&app, account).await?),
        StatusCode::OK,
    ))
}
#[derive(Deserialize)]
struct RecordForm {
    title: String,
    #[serde(default)]
    description: String,
}
fn validate_record(mut value: RecordForm) -> Result<RecordForm> {
    value.title = value.title.trim().into();
    if value.title.is_empty()
        || value.title.chars().count() > 200
        || value.description.len() > 10000
    {
        return Err(StatusCode::BAD_REQUEST);
    }
    Ok(value)
}
async fn create_record(
    State(app): State<Arc<App>>,
    headers: HeaderMap,
    Form(value): Form<RecordForm>,
) -> Result<Response> {
    let account = owner(&app, &headers).await?;
    let value = validate_record(value)?;
    let id: i64 = app
        .database
        .get()
        .await
        .map_err(unavailable)?
        .query_one(
            "insert into records(account_id,title,description) values($1,$2,$3) returning id",
            &[&account, &value.title, &value.description],
        )
        .await
        .map_err(unavailable)?
        .get(0);
    Ok(response(&headers, json!({"id":id}), StatusCode::CREATED))
}
async fn update_record(
    State(app): State<Arc<App>>,
    Path(id): Path<i64>,
    headers: HeaderMap,
    Form(value): Form<RecordForm>,
) -> Result<Response> {
    let account = owner(&app, &headers).await?;
    let value = validate_record(value)?;
    let count = app
        .database
        .get()
        .await
        .map_err(unavailable)?
        .execute(
            "update records set title=$3,description=$4 where id=$1 and account_id=$2",
            &[&id, &account, &value.title, &value.description],
        )
        .await
        .map_err(unavailable)?;
    if count == 0 {
        return Err(StatusCode::NOT_FOUND);
    }
    Ok(response(&headers, json!({"id":id}), StatusCode::OK))
}
async fn delete_record(
    State(app): State<Arc<App>>,
    Path(id): Path<i64>,
    headers: HeaderMap,
) -> Result<Response> {
    let account = owner(&app, &headers).await?;
    let count = app
        .database
        .get()
        .await
        .map_err(unavailable)?
        .execute(
            "delete from records where id=$1 and account_id=$2",
            &[&id, &account],
        )
        .await
        .map_err(unavailable)?;
    if count == 0 {
        return Err(StatusCode::NOT_FOUND);
    }
    Ok(response(&headers, json!({"id":id}), StatusCode::OK))
}
async fn documents(State(app): State<Arc<App>>, headers: HeaderMap) -> Result<Response> {
    let account = owner(&app, &headers).await?;
    let rows = app
        .database
        .get()
        .await
        .map_err(unavailable)?
        .query(
            "select id,file_name,sha256 from documents where account_id=$1 order by id",
            &[&account],
        )
        .await
        .map_err(unavailable)?;
    Ok(response(&headers,json!(rows.iter().map(|r|json!({"id":r.get::<_,i64>(0),"file_name":r.get::<_,String>(1),"sha256":r.get::<_,String>(2)})).collect::<Vec<_>>()),StatusCode::OK))
}
async fn upload(
    State(app): State<Arc<App>>,
    headers: HeaderMap,
    mut multipart: Multipart,
) -> Result<Response> {
    let account = owner(&app, &headers).await?;
    let field = multipart
        .next_field()
        .await
        .map_err(|_| StatusCode::BAD_REQUEST)?
        .ok_or(StatusCode::BAD_REQUEST)?;
    if field.name() != Some("file") {
        return Err(StatusCode::BAD_REQUEST);
    }
    let name = field
        .file_name()
        .ok_or(StatusCode::BAD_REQUEST)?
        .to_string();
    let data = field
        .bytes()
        .await
        .map_err(|_| StatusCode::PAYLOAD_TOO_LARGE)?;
    if data.len() > storage::MAX_UPLOAD_BYTES {
        return Err(StatusCode::PAYLOAD_TOO_LARGE);
    }
    let key = format!("documents/{}", token());
    storage::put(&app.bucket, &key, &data)
        .await
        .map_err(unavailable)?;
    // Keep the immutable object on uncertain database commit; never delete a possibly referenced object.
    let id:i64=app.database.get().await.map_err(unavailable)?.query_one("insert into documents(account_id,object_key,file_name,sha256,byte_count) values($1,$2,$3,$4,$5) returning id", &[&account,&key,&name,&storage::digest(&data),&(data.len() as i64)]).await.map_err(unavailable)?.get(0);
    Ok(response(&headers, json!({"id":id}), StatusCode::CREATED))
}
async fn download(
    State(app): State<Arc<App>>,
    Path(id): Path<i64>,
    headers: HeaderMap,
) -> Result<Response> {
    let account = owner(&app, &headers).await?;
    let conn = app.database.get().await.map_err(unavailable)?;
    let row = conn
        .query_opt(
            "select object_key,sha256 from documents where id=$1 and account_id=$2",
            &[&id, &account],
        )
        .await
        .map_err(unavailable)?
        .ok_or(StatusCode::NOT_FOUND)?;
    let key: String = row.get(0);
    let hash: String = row.get(1);
    drop(conn);
    let data = storage::get(&app.bucket, &key).await.map_err(unavailable)?;
    if storage::digest(&data) != hash {
        return Err(StatusCode::SERVICE_UNAVAILABLE);
    }
    Ok((
        [
            (header::CONTENT_TYPE, "application/octet-stream"),
            (
                header::CONTENT_DISPOSITION,
                "attachment; filename=\"document\"",
            ),
        ],
        data,
    )
        .into_response())
}
async fn reports(State(app): State<Arc<App>>, headers: HeaderMap) -> Result<Response> {
    let account = owner(&app, &headers).await?;
    let rows = app
        .database
        .get()
        .await
        .map_err(unavailable)?
        .query(
            "select id,output from report_jobs where account_id=$1 order by id",
            &[&account],
        )
        .await
        .map_err(unavailable)?;
    Ok(response(
        &headers,
        json!(
            rows.iter()
                .map(|r| json!({"id":r.get::<_,i64>(0),"output":r.get::<_,Option<String>>(1)}))
                .collect::<Vec<_>>()
        ),
        StatusCode::OK,
    ))
}
async fn queue_report(State(app): State<Arc<App>>, headers: HeaderMap) -> Result<Response> {
    let account = owner(&app, &headers).await?;
    let id: i64 = app
        .database
        .get()
        .await
        .map_err(unavailable)?
        .query_one(
            "insert into report_jobs(account_id) values($1) returning id",
            &[&account],
        )
        .await
        .map_err(unavailable)?
        .get(0);
    Ok(response(&headers, json!({"id":id}), StatusCode::CREATED))
}

#[cfg(test)]
mod tests {
    use super::*;
    #[test]
    fn password_limits_and_record_validation() {
        for password in ["short".to_string(), "x".repeat(73)] {
            assert!(
                validate_credentials(Credentials {
                    email: "barbara@example.com".into(),
                    password
                })
                .is_err()
            );
        }
        assert!(
            validate_record(RecordForm {
                title: " ".into(),
                description: String::new()
            })
            .is_err()
        );
        assert!(
            validate_record(RecordForm {
                title: "Invoice".into(),
                description: "x".repeat(10001)
            })
            .is_err()
        );
    }
    #[test]
    fn html_escapes_customer_input() {
        let html = PortalPage {
            records: vec![Record {
                id: 1,
                title: "<script>alert(1)</script>".into(),
                description: "</textarea>".into(),
            }],
            documents: vec![],
            reports: vec![],
        }
        .render()
        .unwrap();
        assert!(!html.contains("<script>"));
        assert!(!html.contains("</textarea></textarea>"));
    }
    #[test]
    fn session_token_is_opaque_and_cookie_parse_is_exact() {
        assert_ne!(token(), token());
        assert_eq!(token().len(), 64);
        let mut headers = HeaderMap::new();
        headers.insert(
            header::COOKIE,
            "other=a; __Host-portal_session=opaque".parse().unwrap(),
        );
        assert_eq!(cookie(&headers).as_deref(), Some("opaque"));
    }
}

#[cfg(test)]
mod security_tests {
    use super::*;
    use tower::ServiceExt;
    fn test_app() -> Router {
        let manager = bb8_postgres::PostgresConnectionManager::new(
            crate::database_config(
                "postgresql://portal@127.0.0.1/portal?target_session_attrs=read-write",
            )
            .unwrap(),
            tokio_postgres::NoTls,
        );
        let database = bb8_postgres::bb8::Pool::builder().build_unchecked(manager);
        let bucket = Bucket::new(
            "test",
            s3::Region::Custom {
                region: "auto".into(),
                endpoint: "https://storage.example.com".into(),
            },
            s3::creds::Credentials::new(Some("invented"), Some("invented"), None, None, None)
                .unwrap(),
        )
        .unwrap();
        routes(Arc::new(App {
            database,
            bucket,
            origin: "https://portal.example.com".into(),
        }))
    }
    #[tokio::test]
    async fn rejects_cross_site_writes_and_protects_cookie() {
        for origin in ["", "null", "https://evil.example.com"] {
            let request = Request::builder()
                .method("POST")
                .uri("/logout")
                .header(header::ORIGIN, origin)
                .body(axum::body::Body::empty())
                .unwrap();
            let response = test_app().oneshot(request).await.unwrap();
            assert_eq!(response.status(), StatusCode::FORBIDDEN);
        }
        let request = Request::builder()
            .method("POST")
            .uri("/logout")
            .header(header::ORIGIN, "https://portal.example.com")
            .header(header::ACCEPT, "application/json")
            .body(axum::body::Body::empty())
            .unwrap();
        let response = test_app().oneshot(request).await.unwrap();
        assert_eq!(response.status(), StatusCode::OK);
        let cookie = response.headers()[header::SET_COOKIE].to_str().unwrap();
        for flag in ["Secure", "HttpOnly", "SameSite=Lax", "Path=/", "Max-Age=0"] {
            assert!(cookie.contains(flag));
        }
    }
    #[tokio::test]
    async fn requires_authentication_before_data_access() {
        for path in ["/records", "/documents", "/documents/1", "/reports"] {
            let request = Request::builder()
                .uri(path)
                .body(axum::body::Body::empty())
                .unwrap();
            assert_eq!(
                test_app().oneshot(request).await.unwrap().status(),
                StatusCode::UNAUTHORIZED
            );
        }
    }
}

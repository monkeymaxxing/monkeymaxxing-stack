mod database;
mod storage;
mod web;

use bb8_postgres::{bb8::Pool, PostgresConnectionManager};
use std::{env, sync::Arc, time::Duration};
use tokio_postgres::NoTls;

type Database = Pool<PostgresConnectionManager<NoTls>>;
type Failure = Box<dyn std::error::Error + Send + Sync>;

fn required(name: &str) -> String {
    env::var(name).unwrap_or_else(|_| panic!("missing environment variable {name}"))
}

fn database_config(value: &str) -> Result<tokio_postgres::Config, Failure> {
    let mut config: tokio_postgres::Config = value.parse().map_err(|_| "invalid DATABASE_URL")?;
    config
        .keepalives(true)
        .keepalives_idle(Duration::from_secs(30));
    // tokio-postgres does not read libpq's PGOPTIONS automatically.
    if let Ok(options) = env::var("PGOPTIONS") {
        config.options(&options);
    }
    Ok(config)
}

fn main() {
    let command = env::args().nth(1).unwrap_or_default();
    let concurrency: usize = env::var("WEB_CONCURRENCY")
        .unwrap_or_else(|_| "1".into())
        .parse()
        .expect("WEB_CONCURRENCY must be a positive integer");
    assert!(concurrency > 0, "WEB_CONCURRENCY must be positive");
    let runtime = tokio::runtime::Builder::new_multi_thread()
        .worker_threads(concurrency)
        .enable_all()
        .build()
        .expect("create Tokio runtime");
    if let Err(error) = runtime.block_on(run(&command)) {
        if command == "seed-test-data" {
            eprintln!("{error}");
        } else {
            eprintln!("command failed; check database/storage availability and settings");
        }
        std::process::exit(1);
    }
}

async fn stop() {
    #[cfg(unix)]
    {
        let mut term = tokio::signal::unix::signal(tokio::signal::unix::SignalKind::terminate())
            .expect("SIGTERM handler");
        tokio::select! { _ = tokio::signal::ctrl_c() => {}, _ = term.recv() => {} }
    }
    #[cfg(not(unix))]
    {
        let _ = tokio::signal::ctrl_c().await;
    }
}

async fn run(command: &str) -> Result<(), Failure> {
    if !["web", "migrate", "jobs", "seed-test-data"].contains(&command) {
        eprintln!("usage: customer_portal web | migrate | jobs | seed-test-data");
        return Err("unknown command".into());
    }
    let mut account_count: i64 = 2;
    if command == "seed-test-data" {
        if !matches!(
            env::var("APP_ENV").as_deref(),
            Ok("development") | Ok("staging")
        ) {
            return Err("seed-test-data refuses to run: APP_ENV must be development or staging, so production never gets test data".into());
        }
        let args: Vec<String> = env::args().skip(2).collect();
        let usage = "Usage: seed-test-data [--accounts N], where N is a whole number of at least 2";
        if !args.is_empty() {
            if args.len() != 2 || args[0] != "--accounts" {
                return Err(usage.into());
            }
            account_count = args[1].parse().map_err(|_| usage)?;
            if account_count < 2 {
                return Err(usage.into());
            }
        }
    }
    let manager =
        PostgresConnectionManager::new(database_config(&required("DATABASE_URL"))?, NoTls);
    let maximum_connections: u32 = env::var("DATABASE_POOL_MAX_CONNECTIONS")
        .unwrap_or_else(|_| "8".into())
        .parse()
        .map_err(|_| "DATABASE_POOL_MAX_CONNECTIONS must be a positive integer")?;
    if maximum_connections == 0 {
        return Err("DATABASE_POOL_MAX_CONNECTIONS must be a positive integer".into());
    }
    let database = Pool::builder()
        .max_size(maximum_connections)
        .connection_timeout(Duration::from_secs(5))
        .build_unchecked(manager);
    match command {
        "migrate" => database::migrate(&database).await?,
        "seed-test-data" => database::seed(&database, &*storage::open()?, account_count).await?,
        "jobs" => {
            let stopped = stop();
            tokio::pin!(stopped);
            loop {
                // Finish an active transaction before observing the stop signal.
                tokio::select! { _ = &mut stopped => break, _ = tokio::time::sleep(Duration::from_secs(1)) => {} }
                if tokio::time::timeout(Duration::from_secs(10), database::run_job(&database))
                    .await
                    .map_or(true, |result| result.is_err())
                {
                    eprintln!("report job failed; unfinished work remains queued");
                }
            }
        }
        "web" => {
            let state = Arc::new(web::App {
                database,
                bucket: storage::open()?,
                origin: required("APP_ORIGIN"),
            });
            let listener =
                tokio::net::TcpListener::bind(format!("0.0.0.0:{}", required("PORT"))).await?;
            axum::serve(listener, web::routes(state))
                .with_graceful_shutdown(stop())
                .await?;
        }
        _ => unreachable!(),
    }
    Ok(())
}

#[cfg(test)]
mod tests {
    use super::*;
    #[test]
    fn keeps_multiple_database_hosts_and_writable_selection() {
        let c = database_config("postgresql://portal:invented@db01:5432,db02:5432/portal?target_session_attrs=read-write&connect_timeout=3").unwrap();
        assert_eq!(c.get_hosts().len(), 2);
        assert_eq!(
            c.get_target_session_attrs(),
            tokio_postgres::config::TargetSessionAttrs::ReadWrite
        );
        assert_eq!(c.get_keepalives_idle(), Duration::from_secs(30));
        assert!(database_config(
            "postgresql://portal@db01/portal?target_session_attrs=prefer-standby"
        )
        .is_err());
    }
}

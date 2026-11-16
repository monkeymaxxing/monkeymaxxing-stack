use crate::{required, storage, Database, Failure};
use s3::Bucket;
use std::{env, time::Duration};

pub const LATEST_MIGRATION: &str = "0002_record_descriptions.sql";
pub async fn migrate(database: &Database) -> Result<(), Failure> {
    for (version, sql) in [
        (
            "0001_portal.sql",
            include_str!("../migrations/0001_portal.sql"),
        ),
        (
            LATEST_MIGRATION,
            include_str!("../migrations/0002_record_descriptions.sql"),
        ),
    ] {
        tokio::time::timeout(Duration::from_secs(30), async {
            let mut conn = database.get().await?;
            let tx = conn.transaction().await?;
            tx.query_one("select pg_advisory_xact_lock(720601)", &[])
                .await?;
            tx.batch_execute(
                "create table if not exists schema_migrations(version text primary key)",
            )
            .await?;
            if !tx
                .query_one(
                    "select exists(select 1 from schema_migrations where version=$1)",
                    &[&version],
                )
                .await?
                .get::<_, bool>(0)
            {
                tx.batch_execute(sql).await?;
                tx.execute("insert into schema_migrations values($1)", &[&version])
                    .await?;
            }
            tx.commit().await?;
            Ok::<_, Failure>(())
        })
        .await??;
    }
    Ok(())
}

pub async fn run_job(database: &Database) -> Result<(), Failure> {
    let mut conn = database.get().await?;
    let tx = conn.transaction().await?;
    if let Some(row) = tx.query_opt("select id,account_id from report_jobs where finished_at is null order by id limit 1 for update skip locked", &[]).await? {
        let id: i64 = row.get(0); let owner: i64 = row.get(1);
        let count: i64 = tx.query_one("select count(*) from records where account_id=$1", &[&owner]).await?.get(0);
        let output = format!("record_count={count}\n");
        tx.execute("update report_jobs set output=$2,finished_at=clock_timestamp() where id=$1", &[&id, &output]).await?;
    }
    tx.commit().await?;
    Ok(())
}

pub async fn seed(database: &Database, bucket: &Bucket, account_count: i64) -> Result<(), Failure> {
    if !matches!(
        env::var("APP_ENV").as_deref(),
        Ok("development") | Ok("staging")
    ) {
        return Err("seed-test-data refuses to run: APP_ENV must be development or staging, so production never gets test data".into());
    }
    let password = required("FIXTURE_PASSWORD");
    if !(12..=72).contains(&password.len()) {
        return Err("FIXTURE_PASSWORD must contain 12 to 72 bytes".into());
    }
    let hash =
        tokio::task::spawn_blocking(move || bcrypt::hash(password, bcrypt::DEFAULT_COST)).await??;
    tokio::time::timeout(Duration::from_secs(30), async {
        let mut conn = database.get().await?;
        let tx = conn.transaction().await?;
        tx.query_one("select pg_advisory_xact_lock(720602)", &[]).await?;
        for (name, description) in [("Barbara", "First synthetic record"), ("Michael", "Second synthetic record")] {
            let email = format!("{}@example.com", name.to_lowercase());
            tx.execute("insert into accounts(email,password_hash) values($1,$2) on conflict(email) do nothing", &[&email, &hash]).await?;
            let owner: i64 = tx.query_one("select id from accounts where email=$1", &[&email]).await?.get(0);
            let title = format!("{name} invoice");
            tx.execute("insert into records(account_id,title,description) select $1::bigint,$2::text,$3::text where not exists(select 1 from records where account_id=$1 and title=$2)", &[&owner, &title, &description]).await?;
            let file_name = format!("{}-note.txt", name.to_lowercase());
            let key = format!("fixtures/{file_name}");
            if !tx.query_one("select exists(select 1 from documents where object_key=$1)", &[&key]).await?.get::<_,bool>(0) {
                let data = format!("{name} synthetic document\n").into_bytes();
                storage::put(bucket, &key, &data).await?;
                tx.execute("insert into documents(account_id,object_key,file_name,sha256,byte_count) values($1,$2,$3,$4,$5)", &[&owner, &key, &file_name, &storage::digest(&data), &(data.len() as i64)]).await?;
            }
            tx.execute("insert into report_jobs(account_id,fixture_key) values($1,$2) on conflict(fixture_key) do nothing", &[&owner, &email]).await?;
        }
        tx.execute("INSERT INTO accounts(email,password_hash)
            SELECT 'test-account-' || repeat('0',greatest(0,6-length(n::text))) || n::text || '@example.com',$2
            FROM generate_series(3,$1::bigint) AS n ON CONFLICT(email) DO NOTHING", &[&account_count, &hash]).await?;
        tx.execute("INSERT INTO records(account_id,title,description)
            SELECT a.id,'Test record ' || n::text,'Generated test record'
            FROM generate_series(3,$1::bigint) AS n
            JOIN accounts a ON a.email='test-account-' || repeat('0',greatest(0,6-length(n::text))) || n::text || '@example.com'
            WHERE NOT EXISTS(SELECT 1 FROM records r WHERE r.account_id=a.id)", &[&account_count]).await?;
        tx.commit().await?;
        Ok::<_, Failure>(())
    }).await??;
    Ok(())
}

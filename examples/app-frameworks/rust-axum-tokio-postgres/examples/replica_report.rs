// tokio-postgres has no prefer-standby setting. Probe the listed hosts, then
// retain the first standby connection. Fall back to a reachable primary.
use std::{env, time::Duration};
use tokio_postgres::{Client, NoTls};
type Failure = Box<dyn std::error::Error + Send + Sync>;
async fn reader(url: &str) -> Result<Client, Failure> {
    let (prefix, tail) = url.rsplit_once('@').ok_or("invalid DATABASE_READ_URL")?;
    let (servers, rest) = tail.split_once('/').ok_or("invalid DATABASE_READ_URL")?;
    let mut primary = None;
    for server in servers.split(',') {
        let candidate = format!(
            "{prefix}@{server}/{}",
            rest.replace(
                "target_session_attrs=prefer-standby",
                "target_session_attrs=any"
            )
        );
        let connected = tokio::time::timeout(Duration::from_secs(4), async {
            let (client, connection) = tokio_postgres::connect(&candidate, NoTls).await?;
            tokio::spawn(async move {
                let _ = connection.await;
            });
            let standby: bool = client
                .query_one("select pg_is_in_recovery()", &[])
                .await?
                .get(0);
            Ok::<_, tokio_postgres::Error>((client, standby))
        })
        .await;
        if let Ok(Ok((client, standby))) = connected {
            if standby {
                return Ok(client);
            }
            if primary.is_none() {
                primary = Some(client);
            }
        }
    }
    primary.ok_or_else(|| "no readable database server answered".into())
}
#[tokio::main]
async fn main() -> Result<(), Failure> {
    let read = reader(&env::var("DATABASE_READ_URL")?).await?;
    let (write, connection) = tokio_postgres::connect(&env::var("DATABASE_URL")?, NoTls).await?;
    tokio::spawn(async move {
        let _ = connection.await;
    });
    for (purpose, client) in [("read", read), ("write", write)] {
        let row = tokio::time::timeout(Duration::from_secs(10), client.query_one("select inet_server_addr()::text, pg_is_in_recovery(), (select count(*) from records)", &[])).await??;
        println!(
            "{}",
            serde_json::json!({"connection_purpose":purpose,"database_server_address":row.get::<_,String>(0),"is_replica":row.get::<_,bool>(1),"record_count":row.get::<_,i64>(2)})
        );
    }
    Ok(())
}

use crate::{Failure, required};
use s3::{Bucket, Region, creds::Credentials};
use sha2::{Digest, Sha256};

pub const MAX_UPLOAD_BYTES: usize = 5 * 1024 * 1024;
pub fn digest(bytes: &[u8]) -> String {
    hex::encode(Sha256::digest(bytes))
}
pub fn open() -> Result<Box<Bucket>, Failure> {
    let credentials = Credentials::new(
        Some(&required("R2_ACCESS_KEY_ID")),
        Some(&required("R2_SECRET_ACCESS_KEY")),
        None,
        None,
        None,
    )?;
    Ok(Bucket::new(
        &required("R2_BUCKET"),
        Region::Custom {
            region: "auto".into(),
            endpoint: required("R2_ENDPOINT"),
        },
        credentials,
    )?
    .with_path_style())
}
pub async fn put(bucket: &Bucket, key: &str, data: &[u8]) -> Result<(), Failure> {
    tokio::time::timeout(
        std::time::Duration::from_secs(10),
        bucket.put_object(key, data),
    )
    .await??;
    Ok(())
}
pub async fn get(bucket: &Bucket, key: &str) -> Result<Vec<u8>, Failure> {
    let result =
        tokio::time::timeout(std::time::Duration::from_secs(10), bucket.get_object(key)).await??;
    if result.as_slice().len() > MAX_UPLOAD_BYTES {
        return Err("stored object exceeds upload limit".into());
    }
    Ok(result.to_vec())
}

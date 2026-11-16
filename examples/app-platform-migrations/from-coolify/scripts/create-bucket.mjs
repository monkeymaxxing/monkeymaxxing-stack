import {S3Client,CreateBucketCommand} from '@aws-sdk/client-s3';
const storage=new S3Client({region:process.env.AWS_REGION,endpoint:process.env.AWS_ENDPOINT_URL_S3,forcePathStyle:true});
await storage.send(new CreateBucketCommand({Bucket:process.env.BUCKET_NAME}));
console.log('Created the dedicated synthetic rehearsal bucket');

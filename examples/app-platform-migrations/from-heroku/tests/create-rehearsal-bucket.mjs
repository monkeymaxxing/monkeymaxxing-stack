import sdk from '../app/node_modules/@aws-sdk/client-s3/dist-cjs/index.js';
const {S3Client,CreateBucketCommand}=sdk;
if(process.env.NODE_ENV!=='test'||process.env.S3_ENDPOINT!=='http://127.0.0.1:9090')throw Error('Create the rehearsal bucket only in the loopback S3 test service');
const client=new S3Client({endpoint:process.env.S3_ENDPOINT,region:process.env.S3_REGION,forcePathStyle:true,credentials:{accessKeyId:process.env.S3_ACCESS_KEY_ID,secretAccessKey:process.env.S3_SECRET_ACCESS_KEY},maxAttempts:1});
await client.send(new CreateBucketCommand({Bucket:process.env.S3_BUCKET}));
console.log('BUCKET_PASS disposable destination bucket created');

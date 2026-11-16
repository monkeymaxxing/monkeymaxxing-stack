// Local protocol/byte-fidelity substitute. This does not prove R2 authorization.
import S3rver from 's3rver';
import { mkdir } from 'node:fs/promises';
const directory=process.env.REHEARSAL_S3_DIR;
if(!directory) throw new Error('REHEARSAL_S3_DIR is required');
await mkdir(directory,{recursive:true,mode:0o700});
const server=new S3rver({port:4569,address:'127.0.0.1',silent:true,directory,
 configureBuckets:[{name:process.env.S3_BUCKET}]});
await server.run();
for(const signal of ['SIGINT','SIGTERM'])process.on(signal,async()=>{await server.close();process.exit(0)});
console.log('S3 rehearsal service ready');

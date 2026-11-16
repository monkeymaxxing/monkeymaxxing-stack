// Run on the trusted operator machine with Application Default Credentials.
// The export contains password hashes and signing material. Never commit it.
import {applicationDefault,initializeApp} from 'firebase-admin/app';
import {getAuth} from 'firebase-admin/auth';
import {getFirestore} from 'firebase-admin/firestore';
import {getStorage} from 'firebase-admin/storage';
import {mkdir,writeFile,readFile,copyFile,chmod} from 'node:fs/promises';
import path from 'node:path';import crypto from 'node:crypto';
process.umask(0o077);
const project=process.env.FIREBASE_PROJECT_ID,bucketName=process.env.FIREBASE_STORAGE_BUCKET,output=path.resolve(process.env.EXPORT_DIR||'migration-export');
if(!project||!bucketName||!process.env.SOURCE_CODE_ARCHIVE)throw Error('FIREBASE_PROJECT_ID, FIREBASE_STORAGE_BUCKET and SOURCE_CODE_ARCHIVE are required');
await mkdir(output,{mode:0o700,recursive:true});await chmod(output,0o700);
const credential=applicationDefault();initializeApp({credential,projectId:project,storageBucket:bucketName});const db=getFirestore();
const control=(await db.doc('controls/runtime').get()).data();
if(!control?.worker_paused||!control?.scheduler_paused||!control?.maintenance)throw Error('Pause source workers and scheduler and enable maintenance before export');
const checksums={};const digest=bytes=>crypto.createHash('sha256').update(bytes).digest('hex');
const save=async(name,data)=>{const bytes=Buffer.from(JSON.stringify(data,null,2)+'\n');await writeFile(path.join(output,name),bytes,{mode:0o600});checksums[name]=digest(bytes);};
const collections={};
for(const collection of await db.listCollections()){
 const snapshot=await collection.get();collections[collection.id]=[];
 for(const document of snapshot.docs){
  if((await document.ref.listCollections()).length)throw Error('Nested collections require an explicit mapping before export: '+document.ref.path);
  collections[collection.id].push({id:document.id,data:document.data()});
 }
 collections[collection.id].sort((a,b)=>a.id.localeCompare(b.id));
}
await save('firestore.json',{collections});
const users=[];let pageToken;
do{
 const page=await getAuth().listUsers(1000,pageToken);pageToken=page.pageToken;
 for(const user of page.users){
  if(!user.passwordHash||!user.passwordSalt)throw Error('A user has no portable Firebase password verifier; decide the reset or reauthentication path before continuing');
  users.push({localId:user.uid,email:user.email,emailVerified:user.emailVerified,disabled:user.disabled,passwordHash:Buffer.from(user.passwordHash,'base64url').toString('base64'),salt:Buffer.from(user.passwordSalt,'base64url').toString('base64'),customAttributes:JSON.stringify(user.customClaims||{}),createdAt:String(Date.parse(user.metadata.creationTime)),lastSignedInAt:String(Date.parse(user.metadata.lastSignInTime))});
 }
}while(pageToken);
users.sort((a,b)=>a.localId.localeCompare(b.localId));await save('users.json',{users});
const token=(await credential.getAccessToken()).access_token;
const response=await fetch(`https://identitytoolkit.googleapis.com/admin/v2/projects/${project}/config`,{headers:{Authorization:`Bearer ${token}`,'x-goog-user-project':project}});
if(!response.ok)throw Error('Auth hash configuration export failed with HTTP '+response.status);
const authConfig=await response.json();if(authConfig.signIn?.hashConfig?.algorithm!=='SCRYPT')throw Error('This example requires Firebase modified SCRYPT; another algorithm needs a separate mapping');
await save('auth-config.json',authConfig);
await mkdir(path.join(output,'objects'),{mode:0o700,recursive:true});
const objects=[];const bucket=getStorage().bucket(bucketName);const [files]=await bucket.getFiles({prefix:'private/'});
const metadata=new Map((collections.documents||[]).map(d=>[d.data.object_key,d.data]));
if(files.length!==metadata.size)throw Error('Private object count differs from document metadata');
for(const file of files){
 const [bytes]=await file.download();const data=metadata.get(file.name);const sha256=digest(bytes);
 if(!data||data.sha256!==sha256||data.byte_length!==bytes.length)throw Error('Object bytes differ from document metadata: '+file.name);
 const relative=`objects/${sha256}`;await writeFile(path.join(output,relative),bytes,{mode:0o600});checksums[relative]=sha256;
 objects.push({object_key:file.name,sha256,byte_length:bytes.length,file:relative});
}
objects.sort((a,b)=>a.object_key.localeCompare(b.object_key));await save('objects.json',objects);
await copyFile(process.env.SOURCE_CODE_ARCHIVE,path.join(output,'source_code.tar.gz'));await chmod(path.join(output,'source_code.tar.gz'),0o600);checksums['source_code.tar.gz']=digest(await readFile(path.join(output,'source_code.tar.gz')));
// Configuration is a separate export from document data. Never guess runtime names.
async function nativeConfig(url) {
 const response=await fetch(url,{headers:{Authorization:`Bearer ${token}`,'x-goog-user-project':project}});
 if(!response.ok)throw Error('Native service configuration export failed with HTTP '+response.status);
 return response.json();
}
const functions=await nativeConfig(`https://cloudfunctions.googleapis.com/v2/projects/${project}/locations/-/functions`);
if(functions.nextPageToken||functions.unreachable?.length)throw Error('Function inventory is incomplete; export all regions/pages before continuing');
await save('native-function-configs.json',functions);
const environmentVariableNames=[...new Set((functions.functions||[]).flatMap(fn=>[...Object.keys(fn.serviceConfig?.environmentVariables||{}),...(fn.serviceConfig?.secretEnvironmentVariables||[]).map(variable=>variable.key)]))].sort();
const regions=[...new Set((functions.functions||[]).map(fn=>fn.name.split('/')[3]))];
const scheduler={jobs:[]};for(const region of regions){const page=await nativeConfig(`https://cloudscheduler.googleapis.com/v1/projects/${project}/locations/${region}/jobs`);if(page.nextPageToken)throw Error('Schedule inventory needs pagination before export');scheduler.jobs.push(...(page.jobs||[]));}
await save('native-scheduler-config.json',scheduler);
await save('native-firestore-config.json',await nativeConfig(`https://firestore.googleapis.com/v1/projects/${project}/databases/(default)`));
await save('native-storage-config.json',(await bucket.getMetadata())[0]);
await save('native-hosting-sites.json',await nativeConfig(`https://firebasehosting.googleapis.com/v1beta1/projects/${project}/sites`));
await save('service-settings.json',{project_id:project,storage_bucket:bucketName,environment_variable_names:environmentVariableNames,source_controls:control,scheduled_tasks:collections.schedules||[],source_schema_migrations:collections.schema_migrations||[],native_configuration_files:['native-function-configs.json','native-scheduler-config.json','native-firestore-config.json','native-storage-config.json','native-hosting-sites.json']});
await writeFile(path.join(output,'manifest.json'),JSON.stringify({version:1,project_id:project,exported_at:new Date().toISOString(),checksums},null,2)+'\n',{mode:0o600});
console.log(JSON.stringify({project_id:project,users:users.length,collections:Object.fromEntries(Object.entries(collections).map(([name,rows])=>[name,rows.length])),private_objects:objects.length,checksums_verified:true}));

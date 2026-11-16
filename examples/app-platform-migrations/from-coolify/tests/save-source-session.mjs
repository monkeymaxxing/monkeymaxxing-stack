import {writeFile} from 'node:fs/promises';
process.umask(0o077);
const response=await fetch(process.env.SOURCE_APP_URL+'/api/login',{method:'POST',headers:{'content-type':'application/json'},body:JSON.stringify({email:'barbara@example.com',password:process.env.FIXTURE_PASSWORD})});
if(!response.ok)throw Error('Source fixture login failed');
await writeFile(process.env.SOURCE_SESSION_FILE,JSON.stringify({user:await response.json(),cookie:response.headers.get('set-cookie').split(';')[0]})+'\n',{flag:'wx',mode:0o600});
console.log('Source session saved in the protected file');

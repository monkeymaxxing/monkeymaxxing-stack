import { readFile, writeFile } from 'node:fs/promises';
import { createHash } from 'node:crypto';
const root=process.env.EXPORT_DIR||process.argv[2]||'/export';
const checksums={};
for(const name of ['source-machines-before-freeze.json','source-machines-paused.json','source-database-volumes.json']){
 const bytes=await readFile(root+'/'+name);JSON.parse(bytes);checksums[name]=createHash('sha256').update(bytes).digest('hex');
}
const before=JSON.parse(await readFile(root+'/source-machines-before-freeze.json','utf8'));
const paused=JSON.parse(await readFile(root+'/source-machines-paused.json','utf8'));
for(const machine of before.filter(m=>m.config?.schedule)){
 const current=paused.find(m=>m.id===machine.id);
 if(!current||current.config?.schedule||current.state!=='stopped')throw Error('A source scheduled Machine is not disabled and stopped');
}
await writeFile(root+'/native-configuration-manifest.json',JSON.stringify({format_version:1,checksums},null,2)+'\n',{mode:0o600});
console.log('Native Machine and Volume inventories checksummed; scheduled Machines are disabled and stopped');

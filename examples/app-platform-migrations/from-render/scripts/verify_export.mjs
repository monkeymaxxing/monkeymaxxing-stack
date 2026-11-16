import {readFile} from 'node:fs/promises';
import {resolve,sep} from 'node:path';
import {createHash} from 'node:crypto';
const dir=resolve(process.env.EXPORT_DIR||'migration-export');
const hash=b=>createHash('sha256').update(b).digest('hex');
const manifest=JSON.parse(await readFile(resolve(dir,'export_manifest.json'),'utf8'));
for(const [name,digest] of Object.entries(manifest.artifacts)){if(!['database.dump','tables.json','objects.json'].includes(name))throw Error('Unexpected artifact name');if(hash(await readFile(resolve(dir,name)))!==digest)throw Error('Export artifact checksum differs: '+name);}
const tables=JSON.parse(await readFile(resolve(dir,'tables.json'),'utf8'));
for(const [name,count] of Object.entries(manifest.table_counts))if(tables[name]?.length!==count)throw Error('Export table count differs: '+name);
for(const doc of manifest.objects){const path=resolve(dir,'objects',doc.object_key);if(!path.startsWith(resolve(dir,'objects')+sep))throw Error('Object key escapes export directory');const bytes=await readFile(path);if(bytes.length!==doc.byte_length||hash(bytes)!==doc.sha256)throw Error('Exported file checksum differs');const row=tables.documents.find(d=>d.id===doc.id);if(!row||row.object_key!==doc.object_key||row.sha256!==doc.sha256||row.owner_id!==doc.owner_id)throw Error('Object manifest differs from database metadata');}
console.log('EXPORT_VERIFIED: artifact checksums, table counts, object ownership and exact bytes');

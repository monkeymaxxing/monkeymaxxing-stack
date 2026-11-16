import { readFile } from 'node:fs/promises';
import { resolve, sep } from 'node:path';
import { createHash } from 'node:crypto';
export async function verifyExport(directory){
 const root=resolve(directory),manifest=JSON.parse(await readFile(root+'/manifest.json','utf8'));
 if(manifest.format_version!==1||!manifest.checksums||!Array.isArray(manifest.files))throw Error('Unsupported export manifest');
 for(const required of ['database.dump','table-audit.json'])if(!manifest.checksums[required])throw Error('Missing checksum: '+required);
 for(const [name,expected] of Object.entries(manifest.checksums)){
  const path=resolve(root,name);if(!path.startsWith(root+sep))throw Error('Export path escapes its directory');
  const actual=createHash('sha256').update(await readFile(path)).digest('hex');if(actual!==expected)throw Error('Export checksum differs: '+name);
 }
 const audit=JSON.parse(await readFile(root+'/table-audit.json','utf8'));
 for(const file of manifest.files){if(manifest.checksums[file.export_path]!==file.sha256)throw Error('File inventory is missing its byte checksum');const bytes=await readFile(root+'/'+file.export_path);if(bytes.length!==file.byte_length)throw Error('File length differs');}
 for(const document of audit.documents){const file=manifest.files.find(f=>f.object_key===document.object_key);if(!file||file.sha256!==document.sha256||String(file.byte_length)!==String(document.byte_length)||manifest.checksums[file.export_path]!==file.sha256)throw Error('Document inventory differs');}
 return {manifest,audit};
}
if(process.argv[1]?.endsWith('/verify-export.mjs')){await verifyExport(process.env.EXPORT_DIR||process.argv[2]||'/export');console.log('Export checksums and document inventory match');}

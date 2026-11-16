import { readExport } from './export_data.mjs';
import { upload, download } from '../storage.mjs';
try {
const data=await readExport();
for (const object of data.objects) {
  const bytes=await data.file(object.file);
  try {
    await upload(object.object_key,bytes);
  } catch(error) {
    // A resumed import may find its own object. Never replace different existing bytes.
    if(error.$metadata?.httpStatusCode!==412)throw error;
    if(!bytes.equals(await download(object.object_key)))throw new Error('Destination already has different bytes at an exported object key.');
  }
  if (!bytes.equals(await download(object.object_key))) throw new Error('Destination object differs from the Firebase export.');
}
console.log(`Imported and downloaded ${data.objects.length} objects with exact byte equality.`);

} catch(error) {
 console.error('Object import failed: '+(error instanceof SyntaxError?'Invalid JSON in protected export.':error.$metadata?.httpStatusCode||error.code||error.name));
 process.exitCode=1;
}

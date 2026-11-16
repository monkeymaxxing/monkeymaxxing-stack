import { readExport } from './export_data.mjs';
try {
const data=await readExport();
console.log(`Verified Firebase export: ${data.users.length} accounts, ${Object.values(data.collections).reduce((n,rows)=>n+rows.length,0)} documents and ${data.objects.length} objects. No secret values were printed.`);

} catch(error) {
 console.error('Export verification failed: '+(error instanceof SyntaxError?'Invalid JSON in protected export.':error.code||error.message));
 process.exitCode=1;
}

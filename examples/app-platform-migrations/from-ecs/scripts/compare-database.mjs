import { verifyExport } from './verify-export.mjs';
import { pool } from '../database.mjs';
const {audit}=await verifyExport(process.env.EXPORT_DIR||'/export');
try{for(const [name,expected] of Object.entries(audit)){if(!/^[a-z_]+$/.test(name))throw Error('Unexpected table name');const actual=(await pool.query('SELECT * FROM "'+name+'" ORDER BY 1')).rows;if(JSON.stringify(actual)!==JSON.stringify(expected))throw Error('Restored table differs: '+name);}console.log('Every restored row equals the source snapshot, including password hashes and owner links');}finally{await pool.end();}

import cluster from 'node:cluster';
import {setTimeout as delay} from 'node:timers/promises';
import {pool,migrate} from './database.mjs';
const command=process.argv[2]||'web';
if(!['web','migrate','jobs','schedule'].includes(command))throw new Error('Command must be web, migrate, jobs, or schedule');
if(command==='web'&&cluster.isPrimary){await migrate();await pool.end();const count=Number(process.env.WEB_CONCURRENCY||1);if(!Number.isInteger(count)||count<1)throw new Error('WEB_CONCURRENCY must be a positive integer');let stopping=false;
 for(let i=0;i<count;i++)cluster.fork();cluster.on('exit',()=>{if(!stopping)cluster.fork();});
 for(const signal of ['SIGTERM','SIGINT'])process.on(signal,()=>{stopping=true;for(const worker of Object.values(cluster.workers))worker.process.kill('SIGTERM');});
}else if(command==='web'){
 const {createServer}=await import('./server.mjs');const server=(await createServer()).listen(Number(process.env.PORT||10000),'0.0.0.0',()=>console.log('Portal web ready'));
 for(const signal of ['SIGTERM','SIGINT'])process.on(signal,()=>server.close(()=>pool.end().then(()=>process.exit(0))));
}else if(command==='migrate'){await migrate();await pool.end();console.log('Migrations complete');
}else{await migrate();const {runReport,runSchedule}=await import('./jobs.mjs');
 if(command==='schedule'){console.log('Schedule occurrence processed:',await runSchedule());await pool.end();}
 else{let stop=false;for(const signal of ['SIGTERM','SIGINT'])process.on(signal,()=>{stop=true;});let nextScheduleCheck=0;while(!stop){await runReport();if(Date.now()>=nextScheduleCheck){if(new Date().getUTCHours()>=3)await runSchedule();nextScheduleCheck=Date.now()+60000;}await delay(500);}await pool.end();}}

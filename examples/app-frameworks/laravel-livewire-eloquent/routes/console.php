<?php
use Illuminate\Support\Facades\Artisan;
use Illuminate\Support\Facades\DB;
use Illuminate\Support\Facades\Hash;
use Illuminate\Support\Facades\Storage;
use App\Models\User;
Artisan::command('portal:jobs {--once}',function () {
 $stopping=false;
 pcntl_async_signals(true);
 pcntl_signal(SIGTERM,function()use(&$stopping){$stopping=true;});
 pcntl_signal(SIGINT,function()use(&$stopping){$stopping=true;});
 do {
     try { $worked=App\Reports::completeNext(); }
     catch (Throwable $error) {
         // Do not log SQL bindings or URLs. A later transaction can reclaim rolled-back work.
         $this->error('Report transaction failed; unfinished work remains queued.'); $worked=false;
         if ($this->option('once')) return 1;
     } finally { DB::disconnect(); }
     if ($this->option('once')) break;
     if (!$worked && !$stopping) usleep(250000);
 } while (!$stopping);
})->purpose('Complete queued reports using PostgreSQL SKIP LOCKED');
Artisan::command('portal:seed-test-data {--accounts=2}',function () {
 if (!in_array(getenv('APP_ENV'),['development','staging'],true)) { $this->error('seed-test-data refuses to run: APP_ENV must be development or staging, so production never gets test data'); return 1; }
 $accounts=$this->option('accounts');
 if (!ctype_digit($accounts) || (int)$accounts<2) { $this->error('Usage: portal:seed-test-data [--accounts N], where N is a whole number of at least 2'); return 1; }
 $password=getenv('FIXTURE_PASSWORD');
 if (!$password || strlen($password)<12 || strlen($password)>72) { $this->error('FIXTURE_PASSWORD must contain 12 to 72 bytes.'); return 1; }
 foreach ([['barbara','Barbara','First'],['michael','Michael','Second']] as [$slug,$name,$ordinal]) {
     $user=User::firstOrCreate(['email'=>"{$slug}@example.com"],['password'=>$password]);
     $user->records()->firstOrCreate(['fixture_key'=>$slug],['title'=>"{$name} invoice",'description'=>"{$ordinal} synthetic record"]);
     if (!$user->documents()->where('fixture_key',$slug)->exists()) {
         $bytes="{$name} synthetic document\n"; $key='fixtures/'.$slug.'-note.txt';
         Storage::disk('s3')->put($key,$bytes,['ContentType'=>'application/octet-stream']);
         $user->documents()->create(['fixture_key'=>$slug,'object_key'=>$key,'file_name'=>$slug.'-note.txt','sha256'=>hash('sha256',$bytes)]);
     }
     $user->reportJobs()->firstOrCreate(['fixture_key'=>$slug]);
 }
 $passwordHash=Hash::make($password);
 DB::transaction(function () use ($accounts,$passwordHash) {
     DB::select('SELECT pg_advisory_xact_lock(20261105)');
     DB::statement("INSERT INTO users(email,password,created_at,updated_at)
         SELECT 'test-account-' || repeat('0',greatest(0,6-length(n::text))) || n::text || '@example.com',?,now(),now()
         FROM generate_series(3,?::bigint) AS n ON CONFLICT(email) DO NOTHING",[$passwordHash,$accounts]);
     DB::statement("INSERT INTO records(user_id,title,description,created_at,updated_at)
         SELECT u.id,'Test record ' || n::text,'Generated test record',now(),now()
         FROM generate_series(3,?::bigint) AS n
         JOIN users u ON u.email='test-account-' || repeat('0',greatest(0,6-length(n::text))) || n::text || '@example.com'
         WHERE NOT EXISTS(SELECT 1 FROM records r WHERE r.user_id=u.id)",[$accounts]);
 });
 $this->info('Synthetic accounts, records, private documents and report jobs are ready.');
 return 0;
})->purpose('Create invented test data without changing existing fixture rows');

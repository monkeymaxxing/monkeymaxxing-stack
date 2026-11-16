<?php
// Administrative aggregate. Web requests and sessions keep the primary.
require 'vendor/autoload.php';
$app=require 'bootstrap/app.php';
$app->make(Illuminate\Contracts\Console\Kernel::class)->bootstrap();
foreach (['read'=>'DATABASE_READ_URL','write'=>'DATABASE_URL'] as $purpose=>$variable) {
 $settings=App\Database\StackDatabaseUrl::settings(getenv($variable));
 config(['database.connections.replica_report'=>array_merge(config('database.connections.pgsql'),$settings)]);
 Illuminate\Support\Facades\DB::purge('replica_report');
 $row=Illuminate\Support\Facades\DB::connection('replica_report')->selectOne('select inet_server_addr()::text as database_server_address, pg_is_in_recovery() as is_replica, (select count(*)::int from records) as record_count');
 echo json_encode(['connection_purpose'=>$purpose]+(array)$row).PHP_EOL;
}

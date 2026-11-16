<?php
return ['default'=>'pgsql', 'connections'=>['pgsql'=>array_merge(
 ['driver'=>'pgsql','charset'=>'utf8','prefix'=>'','application_name'=>'laravel_portal','search_path'=>'public','sslmode'=>'prefer'],
 env('DATABASE_URL') ? App\Database\StackDatabaseUrl::settings(env('DATABASE_URL')) : [])],
 'migrations'=>['table'=>'migrations','update_date_on_publish'=>true]];

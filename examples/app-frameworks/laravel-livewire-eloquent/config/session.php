<?php
return ['driver'=>'database','connection'=>'pgsql','table'=>'sessions','lifetime'=>10080,
 'expire_on_close'=>false,'encrypt'=>false,'files'=>storage_path('framework/sessions'),
 'lottery'=>[2,100],'cookie'=>'laravel_portal_session','path'=>'/','domain'=>null,
 'secure'=>env('SESSION_SECURE_COOKIE',true),'http_only'=>true,'same_site'=>'lax'];

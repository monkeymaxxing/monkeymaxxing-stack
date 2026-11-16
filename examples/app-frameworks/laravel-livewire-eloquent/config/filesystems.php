<?php
return ['default'=>'s3','disks'=>['s3'=>['driver'=>'s3', 'key'=>env('R2_ACCESS_KEY_ID'),
 'secret'=>env('R2_SECRET_ACCESS_KEY'),'region'=>'auto','bucket'=>env('R2_BUCKET'),
 'endpoint'=>env('R2_ENDPOINT'),'use_path_style_endpoint'=>true,'throw'=>true]]];

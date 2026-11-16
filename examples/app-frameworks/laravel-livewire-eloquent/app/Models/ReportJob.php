<?php
namespace App\Models;
final class ReportJob extends \Illuminate\Database\Eloquent\Model
{
 protected $table='report_jobs';
 protected $guarded=['id','user_id'];
}

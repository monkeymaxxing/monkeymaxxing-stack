<?php
namespace App\Models;
final class Document extends \Illuminate\Database\Eloquent\Model
{
 protected $table='documents';
 protected $guarded=['id','user_id'];
}

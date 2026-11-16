<?php
namespace App\Models;
final class CustomerRecord extends \Illuminate\Database\Eloquent\Model
{
 protected $table='records';
 protected $guarded=['id','user_id'];
}

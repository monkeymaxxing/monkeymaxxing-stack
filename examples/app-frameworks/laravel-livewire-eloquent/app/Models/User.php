<?php
namespace App\Models;
use Illuminate\Foundation\Auth\User as Authenticatable;
final class User extends Authenticatable
{
 protected $guarded=['id'];
 protected $hidden=['password','remember_token'];
 protected function casts(): array { return ['password'=>'hashed']; }
 public function records() { return $this->hasMany(CustomerRecord::class); }
 public function documents() { return $this->hasMany(Document::class); }
 public function reportJobs() { return $this->hasMany(ReportJob::class); }
}

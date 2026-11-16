<?php
use Illuminate\Database\Migrations\Migration;
use Illuminate\Database\Schema\Blueprint;
use Illuminate\Support\Facades\Schema;
return new class extends Migration {
 public function up(): void {
 Schema::create('users',function(Blueprint $table){$table->id();$table->string('email')->unique();$table->string('password');$table->rememberToken();$table->timestamps();});
 Schema::create('sessions',function(Blueprint $table){$table->string('id')->primary();$table->foreignId('user_id')->nullable()->index();$table->string('ip_address',45)->nullable();$table->text('user_agent')->nullable();$table->text('payload');$table->integer('last_activity')->index();});
 Schema::create('records',function(Blueprint $table){$table->id();$table->foreignId('user_id')->constrained()->cascadeOnDelete();$table->string('title',200);$table->string('fixture_key')->nullable()->unique();$table->timestamps();});
 Schema::create('documents',function(Blueprint $table){$table->id();$table->foreignId('user_id')->constrained()->cascadeOnDelete();$table->string('object_key')->unique();$table->string('file_name');$table->char('sha256',64);$table->string('fixture_key')->nullable()->unique();$table->timestamps();});
 Schema::create('report_jobs',function(Blueprint $table){$table->id();$table->foreignId('user_id')->constrained()->cascadeOnDelete();$table->string('fixture_key')->nullable()->unique();$table->text('output')->nullable();$table->timestampTz('completed_at')->nullable();$table->timestamps();});
 }
 public function down(): void { foreach(['report_jobs','documents','records','sessions','users'] as $table) Schema::dropIfExists($table); }
};

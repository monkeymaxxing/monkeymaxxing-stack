<?php
namespace App\Providers;
use Illuminate\Support\ServiceProvider;
use Illuminate\Database\Connection;
final class AppServiceProvider extends ServiceProvider
{
 public function register(): void
 {
     $this->app->bind('db.connector.pgsql', \App\Database\StackPostgresConnector::class);
     Connection::resolverFor('pgsql', fn($pdo,$database,$prefix,$config)=>new \App\Database\NoReplayPostgresConnection($pdo,$database,$prefix,$config));
 }
 public function boot(): void
 {
     if (str_starts_with(config('app.url'),'https://')) \Illuminate\Support\Facades\URL::forceScheme('https');
 }
}

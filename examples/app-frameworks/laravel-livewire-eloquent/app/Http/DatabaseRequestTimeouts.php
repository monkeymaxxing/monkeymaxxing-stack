<?php
namespace App\Http;
use Closure;
use Illuminate\Http\Request;
use Illuminate\Support\Facades\DB;
final class DatabaseRequestTimeouts
{
 public function handle(Request $request, Closure $next)
 {
     return DB::transaction(function () use ($request,$next) {
         DB::statement("SET LOCAL statement_timeout = '12s'");
         DB::statement("SET LOCAL lock_timeout = '5s'");
         return $next($request);
     });
 }
}

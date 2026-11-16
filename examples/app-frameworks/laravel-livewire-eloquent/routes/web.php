<?php
use Illuminate\Support\Facades\Route;
use Illuminate\Support\Facades\DB;
use Illuminate\Support\Facades\Schema;
use App\Http\AccountController;
use App\Http\PortalController;
Route::get('/healthz',function () {
 try {
     return DB::transaction(function () {
     DB::statement("SET LOCAL statement_timeout = '2s'");
     $ready=DB::table('migrations')->whereIn('migration',['0001_01_01_000001_create_portal','0001_01_01_000002_record_descriptions'])->count()===2;
     return response()->json(['status'=>$ready?'ok':'migrations pending','release'=>getenv('RELEASE')?:'development'], $ready?200:503);
     });
 } catch (Throwable $error) { return response()->json(['status'=>'database unavailable'],503); }
})->withoutMiddleware(['web']);
Route::view('/login','login')->name('login');
Route::post('/login',[AccountController::class,'login']);
Route::post('/register',[AccountController::class,'register']);
Route::middleware('auth')->group(function () {
 Route::view('/','portal');
 Route::post('/logout',[AccountController::class,'logout']);
 Route::get('/portal',[PortalController::class,'index']);
 Route::post('/records',[PortalController::class,'createRecord']);
 Route::get('/records/{record}',[PortalController::class,'record']);
 Route::patch('/records/{record}',[PortalController::class,'updateRecord']);
 Route::delete('/records/{record}',[PortalController::class,'deleteRecord']);
 Route::post('/documents',[PortalController::class,'upload']);
 Route::get('/documents/{document}',[PortalController::class,'download']);
 Route::post('/reports',[PortalController::class,'queueReport']);
 Route::get('/reports/{report}',[PortalController::class,'report']);
});

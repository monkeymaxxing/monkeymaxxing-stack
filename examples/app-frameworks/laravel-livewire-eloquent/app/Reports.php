<?php
namespace App;
use Illuminate\Support\Facades\DB;
final class Reports
{
 public static function completeNext(): bool
 {
     // One transaction owns reservation, report output, and completion. SIGKILL rolls everything back.
     return DB::transaction(function () {
         DB::statement("SET LOCAL statement_timeout = '12s'");
         DB::statement("SET LOCAL lock_timeout = '5s'");
         $job=DB::table('report_jobs')->whereNull('completed_at')->orderBy('id')->lock('FOR UPDATE SKIP LOCKED')->first();
         if (!$job) return false;
         $count=DB::table('records')->where('user_id',$job->user_id)->count();
         DB::table('report_jobs')->where('id',$job->id)->update(['output'=>"record_count={$count}\n",'completed_at'=>now(),'updated_at'=>now()]);
         return true;
     },1);
 }
}

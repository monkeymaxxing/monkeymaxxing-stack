<?php
namespace App\Http;
use Illuminate\Http\Request;
use Illuminate\Support\Facades\Storage;
use Illuminate\Support\Str;
final class PortalController
{
 public function index(Request $request)
 {
     return response()->json(['user'=>$request->user(),'records'=>$request->user()->records()->orderBy('id')->get(),
         'documents'=>$request->user()->documents()->get(),'reports'=>$request->user()->reportJobs()->get()]);
 }
 public function createRecord(Request $request)
 {
     return response()->json($request->user()->records()->create($request->validate(['title'=>'required|string|max:200','description'=>'sometimes|string|max:4000'])),201);
 }
 public function updateRecord(Request $request, int $record)
 {
     $row=$request->user()->records()->findOrFail($record);
     $row->update($request->validate(['title'=>'required|string|max:200','description'=>'sometimes|string|max:4000']));
     return response()->json($row);
 }
 public function deleteRecord(Request $request, int $record)
 {
     $request->user()->records()->findOrFail($record)->delete(); return response()->noContent();
 }
 public function record(Request $request, int $record) { return response()->json($request->user()->records()->findOrFail($record)); }
 public function upload(Request $request)
 {
     // 8 MiB stays below PHP and Caddy request ceilings and bounds synchronous S3 memory use.
     $request->validate(['document'=>'required|file|max:8192']);
     $file=$request->file('document'); $bytes=file_get_contents($file->getRealPath());
     $key='documents/'.$request->user()->id.'/'.Str::uuid();
     Storage::disk('s3')->put($key,$bytes,['ContentType'=>'application/octet-stream']);
     // Never delete an object after an uncertain database commit. Reconcile retained orphans separately.
     $row=$request->user()->documents()->create(['object_key'=>$key,'file_name'=>basename($file->getClientOriginalName()),'sha256'=>hash('sha256',$bytes)]);
     return $request->expectsJson()?response()->json($row,201):redirect('/');
 }
 public function download(Request $request, int $document)
 {
     $row=$request->user()->documents()->findOrFail($document);
     $bytes=Storage::disk('s3')->get($row->object_key);
     abort_unless(hash_equals($row->sha256,hash('sha256',$bytes)),502,'Stored document checksum does not match.');
     return response($bytes)->header('Content-Type','application/octet-stream')
         ->header('Content-Disposition',\Symfony\Component\HttpFoundation\HeaderUtils::makeDisposition('attachment',$row->file_name,'document'));
 }
 public function queueReport(Request $request) { return response()->json($request->user()->reportJobs()->create([]),202); }
 public function report(Request $request, int $report) { return response()->json($request->user()->reportJobs()->findOrFail($report)); }
}

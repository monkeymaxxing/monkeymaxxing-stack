<?php
namespace App\Livewire;
use Illuminate\Support\Facades\Auth;
use Livewire\Component;
final class Portal extends Component
{
 public string $title='';
 public string $description='';
 public function addRecord(): void
 {
     Auth::user()->records()->create($this->validate(['title'=>'required|string|max:200','description'=>'string|max:4000']));
     $this->reset('title','description');
 }
 public function updateRecord(int $record, string $title, string $description): void
 {
     $row=Auth::user()->records()->findOrFail($record);
     $data=validator(compact('title','description'),['title'=>'required|string|max:200','description'=>'string|max:4000'])->validate();
     $row->update($data);
 }
 public function deleteRecord(int $record): void { Auth::user()->records()->findOrFail($record)->delete(); }
 public function queueReport(): void { Auth::user()->reportJobs()->create([]); }
 public function render()
 {
     return view('livewire.portal',['records'=>Auth::user()->records()->orderBy('id')->get(),
         'documents'=>Auth::user()->documents()->get(),'reports'=>Auth::user()->reportJobs()->orderBy('id')->get()]);
 }
}

<?php
namespace Tests;
use App\Models\User;
use App\Models\CustomerRecord;
use App\Models\ReportJob;
use Illuminate\Support\Facades\DB;
use Livewire\Livewire;
final class PortalLivewireTest extends \Illuminate\Foundation\Testing\TestCase
{
 public function createApplication() { $app=require __DIR__.'/../bootstrap/app.php'; $app->make(\Illuminate\Contracts\Console\Kernel::class)->bootstrap(); return $app; }
 protected function setUp(): void { parent::setUp(); DB::beginTransaction(); }
 protected function tearDown(): void { DB::rollBack(); parent::tearDown(); }
 public function test_owner_can_use_livewire_but_cannot_change_guessed_ids(): void
 {
     $a=User::create(['email'=>'livewire-a@example.com','password'=>str_repeat('x',16)]);
     $b=User::create(['email'=>'livewire-b@example.com','password'=>str_repeat('x',16)]);
     $private=$b->records()->create(['title'=>'Private record']);
     Livewire::actingAs($a)->test(\App\Livewire\Portal::class)->set('title','New record')->set('description','Livewire description')->call('addRecord')->assertHasNoErrors()->assertSee('New record');
     $record=$a->records()->firstOrFail();
     Livewire::actingAs($a)->test(\App\Livewire\Portal::class)->call('updateRecord',$record->id,'Edited title','Edited description')->assertHasNoErrors();
     self::assertSame('Edited title',$record->fresh()->title);
     Livewire::actingAs($a)->test(\App\Livewire\Portal::class)->call('updateRecord',$private->id,'Stolen','Stolen')->assertNotFound();
     Livewire::actingAs($a)->test(\App\Livewire\Portal::class)->call('deleteRecord',$private->id)->assertNotFound();
     self::assertSame('Private record',$private->fresh()->title);
     Livewire::actingAs($a)->test(\App\Livewire\Portal::class)->call('queueReport');
     self::assertSame(1,$a->reportJobs()->count());
     Livewire::actingAs($a)->test(\App\Livewire\Portal::class)->call('deleteRecord',$record->id);
     self::assertNull($record->fresh());
 }
}

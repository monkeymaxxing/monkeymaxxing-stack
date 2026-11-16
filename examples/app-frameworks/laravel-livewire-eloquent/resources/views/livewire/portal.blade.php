<div wire:poll.5s>
<h2>Your records</h2>
<form wire:submit="addRecord"><label>Title <input wire:model="title" required maxlength="200"></label><label>Description <textarea wire:model="description" maxlength="4000"></textarea></label><button>Add record</button></form>
@error('title')<p role="alert">{{ $message }}</p>@enderror
<ul>@foreach($records as $record)<li wire:key="record-{{ $record->id }}" x-data="{ title: @js($record->title), description: @js($record->description) }">
<label>Title <input x-model="title"></label><label>Description <textarea x-model="description"></textarea></label>
<button x-on:click="$wire.updateRecord({{ $record->id }}, title, description)">Save record</button>
<button wire:click="deleteRecord({{ $record->id }})">Delete record</button></li>@endforeach</ul>
<h2>Your private documents</h2><form method="post" action="/documents" enctype="multipart/form-data">@csrf<label>Document (up to 8 MiB) <input type="file" name="document" required></label><button>Upload document</button></form>
<ul>@foreach($documents as $document)<li><a href="/documents/{{ $document->id }}">{{ $document->file_name }}</a></li>@endforeach</ul>
<h2>Your reports</h2><button wire:click="queueReport">Request record count</button>
<ul>@foreach($reports as $report)<li>Report {{ $report->id }}: {{ $report->completed_at ? $report->output : 'Waiting for a worker' }}</li>@endforeach</ul>
</div>

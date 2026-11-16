@extends('layout')
@section('content')
<p>Signed in as {{ auth()->user()->email }}</p><form method="post" action="/logout">@csrf<button>Sign out</button></form>
<livewire:portal />
@endsection

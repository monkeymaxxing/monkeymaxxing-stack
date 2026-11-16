@extends('layout')
@section('content')
<h2>Sign in</h2><form method="post" action="/login">@csrf<label>Email <input name="email" type="email" required autocomplete="email"></label><label>Password <input name="password" type="password" required autocomplete="current-password"></label><button>Sign in</button></form>
<h2>Create an account</h2><p>Use a password with 12 to 72 characters.</p><form method="post" action="/register">@csrf<label>Email <input name="email" type="email" required autocomplete="email"></label><label>Password <input name="password" type="password" minlength="12" maxlength="72" required autocomplete="new-password"></label><button>Create account</button></form>
@if($errors->any())<p role="alert">{{ $errors->first() }}</p>@endif
@endsection

<?php
use Illuminate\Foundation\Application;
use Illuminate\Foundation\Configuration\Exceptions;
use Illuminate\Foundation\Configuration\Middleware;
return Application::configure(basePath: dirname(__DIR__))
 ->withRouting(web: __DIR__.'/../routes/web.php', commands: __DIR__.'/../routes/console.php')
 ->withMiddleware(function (Middleware $middleware) {
     // Start the transaction before session and authentication database reads.
     // Health excludes the web group and retains its separate two-second deadline.
     $middleware->web(prepend: [App\Http\DatabaseRequestTimeouts::class]);
     $middleware->append(App\Http\PrivateResponses::class);
     $middleware->redirectGuestsTo('/login');
 })
 ->withExceptions(function (Exceptions $exceptions) {
     // Query errors can contain bindings. Return and log no customer data or credentials.
     $exceptions->report(function (Illuminate\Database\QueryException $error) { return false; });
     $exceptions->render(function (Illuminate\Database\QueryException $error, Illuminate\Http\Request $request) {
         return response()->json(['message'=>'Database request failed. Check the result before trying a change again.'], 503);
     });
 })->create();

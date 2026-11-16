<?php
namespace App\Database;
use Closure;
use Illuminate\Database\QueryException;
final class NoReplayPostgresConnection extends \Illuminate\Database\PostgresConnection
{
 protected function tryAgainIfCausedByLostConnection(QueryException $error, $query, $bindings, Closure $callback)
 {
     // The server may have committed before the reply disappeared. Never repeat the query.
     $this->disconnect();
     throw $error;
 }
}

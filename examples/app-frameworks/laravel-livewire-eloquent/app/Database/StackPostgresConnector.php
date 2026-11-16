<?php
namespace App\Database;
final class StackPostgresConnector extends \Illuminate\Database\Connectors\PostgresConnector
{
 protected function getDsn(array $config)
 {
     // PDO::ATTR_TIMEOUT controls libpq's connect_timeout. Persistent PDO
     // connections avoid probing a dead first host on every PHP request.
     return parent::getDsn($config).';target_session_attrs='.($config['target_session_attrs']??'read-write')
         .';keepalives=1;keepalives_idle=30;keepalives_interval=5;keepalives_count=3;tcp_user_timeout=10000';
 }
 public function connect(array $config)
 {
     if (empty($config['host'])) throw new \InvalidArgumentException('DATABASE_URL is required for database commands and requests.');
     $pdo=parent::connect($config);
     return $pdo;
 }
}

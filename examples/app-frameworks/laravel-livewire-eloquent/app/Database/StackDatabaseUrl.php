<?php
namespace App\Database;
use InvalidArgumentException;
use PDO;
final class StackDatabaseUrl
{
 public static function settings(string $url): array
 {
     if (!preg_match('~^postgres(?:ql)?://([^:@/]+):([^@/]*)@([^/?]+)/([^/?]+)\?([^#]+)$~D', $url, $parts)) {
         throw new InvalidArgumentException('DATABASE_URL must contain encoded credentials, host:port entries, database, target_session_attrs and connect_timeout.');
     }
     [, $user, $password, $serverList, $database, $query] = $parts;
     parse_str($query, $settings);
     if (array_diff(array_keys($settings), ['target_session_attrs','connect_timeout','sslmode']) ||
         !in_array($settings['target_session_attrs']??'', ['read-write','prefer-standby'], true) ||
         !ctype_digit((string)($settings['connect_timeout']??'')) || (int)$settings['connect_timeout']<1) {
         throw new InvalidArgumentException('DATABASE_URL requires target_session_attrs=read-write or prefer-standby and a positive connect_timeout. Only sslmode is optional.');
     }
     $hosts=[]; $ports=[];
     foreach (explode(',', $serverList) as $server) {
         if (!preg_match('/^(\[[0-9a-fA-F:]+\]|[a-zA-Z0-9_.-]+):([0-9]+)$/D',$server,$match) || (int)$match[2]<1 || (int)$match[2]>65535) {
             throw new InvalidArgumentException('Every database server must contain host:port.');
         }
         $hosts[]=trim($match[1],'[]'); $ports[]=$match[2];
     }
     $database=rawurldecode($database);
     if (!preg_match('/^[a-zA-Z0-9_]+$/D',$database)) throw new InvalidArgumentException('Database names must contain letters, numbers or underscores for safe DSN construction.');
     $sslmode=$settings['sslmode']??'prefer';
     if (!in_array($sslmode,['disable','allow','prefer','require','verify-ca','verify-full'],true)) throw new InvalidArgumentException('Unsupported database sslmode.');
     return ['host'=>implode(',',$hosts),'port'=>implode(',',$ports),'database'=>$database,
         'username'=>rawurldecode($user),'password'=>rawurldecode($password),
         'sslmode'=>$sslmode,'target_session_attrs'=>$settings['target_session_attrs'],'options'=>[PDO::ATTR_TIMEOUT=>(int)$settings['connect_timeout'], PDO::ATTR_PERSISTENT=>true, PDO::PGSQL_ATTR_DISABLE_PREPARES=>true]];
 }
}

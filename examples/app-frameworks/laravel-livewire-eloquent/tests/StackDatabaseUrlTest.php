<?php
namespace Tests;
use App\Database\StackDatabaseUrl;
use App\Database\NoReplayPostgresConnection;
use Illuminate\Database\QueryException;
use PHPUnit\Framework\TestCase;
final class StackDatabaseUrlTest extends TestCase
{
 public function test_multiple_hosts_encoded_credentials_and_deadline(): void
 {
     $config=StackDatabaseUrl::settings('postgresql://some%40user:some%3B%27password@db02:6432,[::1]:5432/portal?target_session_attrs=read-write&connect_timeout=3');
     self::assertSame('db02,::1',$config['host']); self::assertSame('6432,5432',$config['port']);
     self::assertSame('some@user',$config['username']); self::assertSame("some;'password",$config['password']);
     self::assertSame(3,$config['options'][\PDO::ATTR_TIMEOUT]);
 }
 public function test_persistent_connection_keeps_timeout_and_replica_preference(): void
 {
     $config=StackDatabaseUrl::settings('postgresql://user:invented@db01:5432,db02:5432/portal?target_session_attrs=prefer-standby&connect_timeout=3');
     $method=new \ReflectionMethod(\App\Database\StackPostgresConnector::class, 'getDsn');
     $dsn=$method->invoke(new \App\Database\StackPostgresConnector(), $config+['charset'=>'utf8','sslmode'=>'prefer']);
     self::assertStringContainsString('target_session_attrs=prefer-standby',$dsn);
     self::assertSame(3,$config['options'][\PDO::ATTR_TIMEOUT]);
     self::assertTrue($config['options'][\PDO::ATTR_PERSISTENT]);
     self::assertTrue($config['options'][\PDO::PGSQL_ATTR_DISABLE_PREPARES]);
     self::assertStringContainsString('tcp_user_timeout=10000',$dsn);
 }
 public function test_unsupported_url_setting_is_refused(): void
 {
     $this->expectException(\InvalidArgumentException::class);
     StackDatabaseUrl::settings('postgresql://user:password@db01:5432/portal?target_session_attrs=read-write&connect_timeout=3&ignored=true');
 }
 public function test_uncertain_query_is_never_replayed(): void
 {
     $executions=0;
     $statement=$this->createMock(\PDOStatement::class);
     $statement->expects(self::once())->method('execute')->willReturnCallback(function()use(&$executions){$executions++;throw new \PDOException('server closed the connection unexpectedly');});
     $pdo=$this->createMock(\PDO::class);
     $pdo->expects(self::once())->method('prepare')->willReturn($statement);
     $connection=new NoReplayPostgresConnection($pdo,'portal');
     $reconnected=false;
     $connection->setReconnector(function()use(&$reconnected){$reconnected=true;});
     try { $connection->insert('insert into records(title) values (?)',['example']); self::fail('Query error was swallowed'); }
     catch(QueryException $caught) { self::assertStringContainsString('server closed the connection',$caught->getMessage()); }
     self::assertSame(1,$executions);
     self::assertFalse($reconnected);
 }
}

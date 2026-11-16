package main

import (
	"context"
	"embed"
	"fmt"
	"io/fs"
	"os"
	"strings"
	"time"

	"github.com/jackc/pgx/v5/pgxpool"
	"golang.org/x/crypto/bcrypt"
)

//go:embed migrations/*.sql
var migrations embed.FS

const latestMigration = "0002_record_descriptions.sql"

func migrate(database *pgxpool.Pool) error {
	files, err := fs.Glob(migrations, "migrations/*.sql")
	if err != nil {
		return err
	}
	for _, file := range files {
		ctx, cancel := context.WithTimeout(context.Background(), 30*time.Second)
		err = func() error {
			tx, err := database.Begin(ctx)
			if err != nil {
				return err
			}
			defer tx.Rollback(ctx)
			if _, err = tx.Exec(ctx, "select pg_advisory_xact_lock(720601)"); err != nil {
				return err
			}
			if _, err = tx.Exec(ctx, "create table if not exists schema_migrations(version text primary key)"); err != nil {
				return err
			}
			var exists bool
			version := strings.TrimPrefix(file, "migrations/")
			if err = tx.QueryRow(ctx, "select exists(select 1 from schema_migrations where version=$1)", version).Scan(&exists); err != nil {
				return err
			}
			if exists {
				return tx.Commit(ctx)
			}
			sql, _ := migrations.ReadFile(file)
			if _, err = tx.Exec(ctx, string(sql)); err != nil {
				return err
			}
			if _, err = tx.Exec(ctx, "insert into schema_migrations values($1)", version); err != nil {
				return err
			}
			return tx.Commit(ctx)
		}()
		cancel()
		if err != nil {
			return err
		}
	}
	return nil
}

func seed(database *pgxpool.Pool, storage *objectStorage, accountCount int64) error {
	if os.Getenv("APP_ENV") != "development" && os.Getenv("APP_ENV") != "staging" {
		return fmt.Errorf("seed-test-data refuses to run: APP_ENV must be development or staging, so production never gets test data")
	}
	password := required("FIXTURE_PASSWORD")
	if len(password) < 12 || len(password) > 72 {
		return fmt.Errorf("FIXTURE_PASSWORD must contain 12 to 72 bytes")
	}
	hash, err := bcrypt.GenerateFromPassword([]byte(password), bcrypt.DefaultCost)
	if err != nil {
		return err
	}
	ctx, cancel := context.WithTimeout(context.Background(), 30*time.Second)
	defer cancel()
	tx, err := database.Begin(ctx)
	if err != nil {
		return err
	}
	defer tx.Rollback(ctx)
	if _, err = tx.Exec(ctx, "select pg_advisory_xact_lock(720602)"); err != nil {
		return err
	}
	for i, name := range []string{"Barbara", "Michael"} {
		email := strings.ToLower(name) + "@example.com"
		var id int64
		if _, err = tx.Exec(ctx, "insert into accounts(email,password_hash) values($1,$2) on conflict(email) do nothing", email, string(hash)); err != nil {
			return err
		}
		if err = tx.QueryRow(ctx, "select id from accounts where email=$1", email).Scan(&id); err != nil {
			return err
		}
		title := name + " invoice"
		description := []string{"First synthetic record", "Second synthetic record"}[i]
		if _, err = tx.Exec(ctx, "insert into records(account_id,title,description) select $1::bigint,$2::text,$3::text where not exists(select 1 from records where account_id=$1 and title=$2)", id, title, description); err != nil {
			return err
		}
		key := "fixtures/" + strings.ToLower(name) + "-note.txt"
		var exists bool
		if err = tx.QueryRow(ctx, "select exists(select 1 from documents where object_key=$1)", key).Scan(&exists); err != nil {
			return err
		}
		if !exists {
			data := []byte(name + " synthetic document\n")
			if err = storage.put(ctx, key, data); err != nil {
				return err
			}
			if _, err = tx.Exec(ctx, "insert into documents(account_id,object_key,file_name,sha256,byte_count) values($1,$2,$3,$4,$5)", id, key, strings.ToLower(name)+"-note.txt", digest(data), len(data)); err != nil {
				return err
			}
		}
		if _, err = tx.Exec(ctx, "insert into report_jobs(account_id,fixture_key) values($1,$2) on conflict(fixture_key) do nothing", id, email); err != nil {
			return err
		}
	}
	if _, err = tx.Exec(ctx, `INSERT INTO accounts(email,password_hash)
        SELECT 'test-account-' || repeat('0',greatest(0,6-length(n::text))) || n::text || '@example.com',$2
        FROM generate_series(3,$1::bigint) AS n ON CONFLICT(email) DO NOTHING`, accountCount, string(hash)); err != nil {
		return err
	}
	if _, err = tx.Exec(ctx, `INSERT INTO records(account_id,title,description)
        SELECT a.id,'Test record ' || n::text,'Generated test record'
        FROM generate_series(3,$1::bigint) AS n
        JOIN accounts a ON a.email='test-account-' || repeat('0',greatest(0,6-length(n::text))) || n::text || '@example.com'
        WHERE NOT EXISTS(SELECT 1 FROM records r WHERE r.account_id=a.id)`, accountCount); err != nil {
		return err
	}
	return tx.Commit(ctx)
}

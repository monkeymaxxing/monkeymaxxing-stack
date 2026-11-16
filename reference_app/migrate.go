package main

import (
	"context"
	"embed"
	"fmt"
	"io/fs"
	"log"
	"path"
	"strings"

	"github.com/jackc/pgx/v5/pgxpool"
)

// The migrations are plain SQL files, built into the program, so each
// release carries exactly the migrations it knows.
//
//go:embed migrations/*.sql
var migrationFiles embed.FS

// migrationVersions lists the migrations this release knows, in the order
// they apply: the file names in migrations/, sorted, without ".sql".
var migrationVersions = listMigrationVersions()

// newestMigrationVersion is the last migration this release knows. The
// health URL passes only once it is applied.
var newestMigrationVersion = migrationVersions[len(migrationVersions)-1]

// migrationLockKey names the advisory lock that lets one migrate run at a
// time in the app's database. Two app servers that start at once both run
// migrate: the second waits for the first, then finds its work done.
const migrationLockKey = 1

func listMigrationVersions() []string {
	paths, err := fs.Glob(migrationFiles, "migrations/*.sql") // sorted by name
	if err != nil || len(paths) == 0 {
		panic("the program holds no migrations")
	}
	versions := make([]string, len(paths))
	for i, filePath := range paths {
		versions[i] = strings.TrimSuffix(path.Base(filePath), ".sql")
	}
	return versions
}

// migrate applies, in order, each migration that schema_migrations doesn't
// list yet. Running it again changes nothing.
func migrate() error {
	database, err := openDatabase()
	if err != nil {
		return err
	}
	defer database.Close()

	appliedCount := 0
	for _, version := range migrationVersions {
		applied, err := applyMigration(context.Background(), database, version)
		if err != nil {
			return fmt.Errorf("migration %s: %w", version, err)
		}
		if applied {
			log.Printf("migrate: applied %s", version)
			appliedCount++
		}
	}
	if appliedCount == 0 {
		log.Printf("migrate: nothing to do, all %d migrations were already applied", len(migrationVersions))
	}
	return nil
}

// applyMigration applies one migration and records it in schema_migrations,
// in one transaction, unless it is recorded already. It reports whether it
// applied the migration.
func applyMigration(ctx context.Context, database *pgxpool.Pool, version string) (bool, error) {
	sql, err := migrationFiles.ReadFile("migrations/" + version + ".sql")
	if err != nil {
		return false, err
	}
	transaction, err := database.Begin(ctx)
	if err != nil {
		return false, err
	}
	// After a commit, the rollback does nothing.
	defer transaction.Rollback(ctx)

	// The lock is released when the transaction ends.
	if _, err := transaction.Exec(ctx, "select pg_advisory_xact_lock($1)", migrationLockKey); err != nil {
		return false, err
	}
	if _, err := transaction.Exec(ctx, `
		create table if not exists schema_migrations (
		  version text primary key,
		  applied_at timestamptz not null default now()
		)`); err != nil {
		return false, err
	}
	var alreadyApplied bool
	if err := transaction.QueryRow(ctx,
		"select exists (select 1 from schema_migrations where version = $1)", version,
	).Scan(&alreadyApplied); err != nil {
		return false, err
	}
	if alreadyApplied {
		return false, nil
	}
	// Without arguments, pgx sends the file as it is, so it may hold
	// several statements.
	if _, err := transaction.Exec(ctx, string(sql)); err != nil {
		return false, err
	}
	if _, err := transaction.Exec(ctx, "insert into schema_migrations (version) values ($1)", version); err != nil {
		return false, err
	}
	return true, transaction.Commit(ctx)
}

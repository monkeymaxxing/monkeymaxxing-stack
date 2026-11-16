// Command reference_app is the app that the Monkeymaxxing Stack's proofs
// and courses deploy. Its home page shows which app server and which
// database server answered, so a deploy, a database failover, or a restore
// shows on the page while it happens.
//
// It is one program with five subcommands:
//
//	reference_app web            the web server, on the port in PORT
//	reference_app migrate        applies the database migrations
//	reference_app jobs           the job worker
//	reference_app write-assets   writes the asset files; the Containerfile runs it
//	reference_app seed-test-data   fills development or staging with invented test data
//
// Its settings come from environment variables: PORT, for web only;
// DATABASE_URL; and DATABASE_READ_URL, for web only, for the reads that may
// be a moment behind the primary.
package main

import (
	"context"
	"fmt"
	"log"
	"os"

	"github.com/jackc/pgx/v5/pgxpool"
)

// release is the release this program was built from, such as the commit
// that CI built. The Containerfile sets it with -ldflags.
var release = "development"

const usage = `usage: reference_app web | migrate | jobs | write-assets | seed-test-data`

func main() {
	log.SetOutput(os.Stdout)
	// The journal adds the time to each line.
	log.SetFlags(0)

	if len(os.Args) != 2 {
		log.Fatal(usage)
	}
	var err error
	switch os.Args[1] {
	case "web":
		err = runWebServer()
	case "migrate":
		err = migrate()
	case "jobs":
		err = runJobWorker()
	case "write-assets":
		err = writeAssets()
	case "seed-test-data":
		err = seedTestData()
	default:
		log.Fatal(usage)
	}
	if err != nil {
		log.Fatalf("reference_app %s: %v", os.Args[1], err)
	}
}

// requiredSetting returns the value of the environment variable name, or
// an error that names the variable.
func requiredSetting(name string) (string, error) {
	value := os.Getenv(name)
	if value == "" {
		return "", fmt.Errorf("the environment variable %s is not set", name)
	}
	return value, nil
}

// openDatabase makes the pool of connections to the database that
// DATABASE_URL names, such as
// postgresql://reference_app:PASSWORD@10.20.2.1,10.20.2.2/reference_app?target_session_attrs=read-write&connect_timeout=3.
// pgx tries the servers in turn and keeps only one that accepts writes, so
// after a database failover new connections reach the new primary;
// connect_timeout limits how long it waits for a server that is switched
// off before it tries the next one. The pool connects when a connection is
// first needed: the program starts even while no database server answers.
func openDatabase() (*pgxpool.Pool, error) {
	return openDatabaseOfSetting("DATABASE_URL")
}

// openReadDatabase makes the pool of connections for reads that may be a
// moment behind the primary, from DATABASE_READ_URL, which lists the same
// servers with target_session_attrs=prefer-standby: pgx keeps a replica
// when one answers, and the primary otherwise.
func openReadDatabase() (*pgxpool.Pool, error) {
	return openDatabaseOfSetting("DATABASE_READ_URL")
}

func openDatabaseOfSetting(setting string) (*pgxpool.Pool, error) {
	databaseURL, err := requiredSetting(setting)
	if err != nil {
		return nil, err
	}
	config, err := pgxpool.ParseConfig(databaseURL)
	if err != nil {
		return nil, fmt.Errorf("%s: %w", setting, err)
	}
	return pgxpool.NewWithConfig(context.Background(), config)
}

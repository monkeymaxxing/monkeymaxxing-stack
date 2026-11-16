// Customer portal: a standalone net/http example for the Stack.
package main

import (
	"context"
	"fmt"
	"log"
	"net"
	"net/http"
	"os"
	"os/signal"
	"runtime"
	"strconv"
	"syscall"
	"time"

	"github.com/jackc/pgx/v5/pgxpool"
)

var release = "development"

func required(name string) string {
	value := os.Getenv(name)
	if value == "" {
		panic("missing environment variable " + name)
	}
	return value
}

func databaseConfig(value string) (*pgxpool.Config, error) {
	config, err := pgxpool.ParseConfig(value)
	if err != nil {
		return nil, fmt.Errorf("invalid DATABASE_URL")
	}
	dialer := &net.Dialer{Timeout: config.ConnConfig.ConnectTimeout,
		KeepAliveConfig: net.KeepAliveConfig{Enable: true, Idle: -1, Interval: -1, Count: -1}}
	config.ConnConfig.DialFunc = dialer.DialContext
	maximumConnections, err := strconv.ParseInt(os.Getenv("DATABASE_POOL_MAX_CONNECTIONS"), 10, 32)
	if os.Getenv("DATABASE_POOL_MAX_CONNECTIONS") == "" {
		maximumConnections = 8
	} else if err != nil || maximumConnections < 1 {
		return nil, fmt.Errorf("DATABASE_POOL_MAX_CONNECTIONS must be a positive integer")
	}
	config.MaxConns = int32(maximumConnections)
	// PGOPTIONS from the Stack's migration runner must reach Postgres.
	return config, nil
}

func main() {
	log.SetFlags(0)
	if len(os.Args) < 2 {
		log.Fatal("usage: customer_portal web | migrate | jobs | seed-test-data")
	}
	accountCount := int64(2)
	if os.Args[1] == "seed-test-data" {
		if os.Getenv("APP_ENV") != "development" && os.Getenv("APP_ENV") != "staging" {
			log.Fatal("seed-test-data refuses to run: APP_ENV must be development or staging, so production never gets test data")
		}
		if len(os.Args) != 2 {
			var parseErr error
			if len(os.Args) == 4 && os.Args[2] == "--accounts" {
				accountCount, parseErr = strconv.ParseInt(os.Args[3], 10, 64)
			} else {
				parseErr = fmt.Errorf("invalid arguments")
			}
			if parseErr != nil || accountCount < 2 {
				log.Fatal("Usage: seed-test-data [--accounts N], where N is a whole number of at least 2")
			}
		}
	} else if len(os.Args) != 2 {
		log.Fatal("usage: customer_portal web | migrate | jobs | seed-test-data")
	}
	config, err := databaseConfig(required("DATABASE_URL"))
	if err != nil {
		log.Fatal(err)
	}
	database, err := pgxpool.NewWithConfig(context.Background(), config)
	if err != nil {
		log.Fatal("cannot create database pool")
	}
	defer database.Close()
	stop, cancel := signal.NotifyContext(context.Background(), os.Interrupt, syscall.SIGTERM)
	defer cancel()
	switch os.Args[1] {
	case "migrate":
		err = migrate(database)
	case "jobs":
		err = worker(stop, database)
	case "seed-test-data":
		err = seed(database, openStorage(), accountCount)
	case "web":
		if value := os.Getenv("WEB_CONCURRENCY"); value != "" {
			count, parseErr := strconv.Atoi(value)
			if parseErr != nil || count < 1 {
				log.Fatal("WEB_CONCURRENCY must be a positive integer")
			}
			runtime.GOMAXPROCS(count) // Go serves concurrent requests in goroutines, not child processes.
		}
		portal := &app{database: database, storage: openStorage(), origin: required("APP_ORIGIN")}
		server := &http.Server{Addr: net.JoinHostPort("", required("PORT")), Handler: portal.routes(),
			ReadHeaderTimeout: 5 * time.Second, ReadTimeout: 15 * time.Second, WriteTimeout: 15 * time.Second, IdleTimeout: 60 * time.Second}
		shutdownDone := make(chan struct{})
		go func() {
			defer close(shutdownDone)
			<-stop.Done()
			ctx, done := context.WithTimeout(context.Background(), 25*time.Second)
			defer done()
			server.Shutdown(ctx)
		}()
		err = server.ListenAndServe()
		if err == http.ErrServerClosed {
			<-shutdownDone
			err = nil
		}
	default:
		log.Fatal("unknown command")
	}
	if err != nil {
		if os.Args[1] == "seed-test-data" {
			log.Fatal(err)
		}
		log.Fatal("command failed; check database/storage availability and settings")
	}
}

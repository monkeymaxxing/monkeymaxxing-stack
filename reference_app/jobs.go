package main

import (
	"context"
	"errors"
	"log"
	"os"
	"os/signal"
	"syscall"
	"time"

	"github.com/jackc/pgx/v5"
	"github.com/jackc/pgx/v5/pgxpool"
)

// runJobWorker runs the jobs in the jobs table, oldest first, one at a
// time, until the stop signal. Then it finishes the job it is running and
// exits. One worker runs on each app server, and they share the queue.
func runJobWorker() error {
	database, err := openDatabase()
	if err != nil {
		return err
	}
	defer database.Close()
	hostName, err := os.Hostname()
	if err != nil {
		return err
	}
	stop, stopListening := signal.NotifyContext(context.Background(), syscall.SIGTERM, os.Interrupt)
	defer stopListening()

	log.Printf("jobs: release %s on %s, waiting for jobs", release, hostName)
	for stop.Err() == nil {
		ranAJob, err := runOneJob(database, hostName)
		var wait time.Duration
		switch {
		case err != nil:
			// Such as while the database fails over: the worker tries again,
			// as often as it takes, and never exits for it.
			log.Printf("jobs: %v; trying again in 5 seconds", err)
			wait = 5 * time.Second
		case !ranAJob:
			wait = time.Second
		}
		select {
		case <-stop.Done():
		case <-time.After(wait):
		}
	}
	log.Print("jobs: stopped")
	return nil
}

// runOneJob takes the oldest waiting job, does its work, and records when
// it finished and on which server. It reports whether there was a job.
//
// The job's row stays locked until its transaction commits: every other
// worker skips it (SKIP LOCKED), and if this worker dies first, Postgres
// releases the lock and the job waits for the next worker.
func runOneJob(database *pgxpool.Pool, hostName string) (bool, error) {
	// Not the stop signal's context: a job that has started finishes.
	ctx, cancel := context.WithTimeout(context.Background(), 10*time.Second)
	defer cancel()
	transaction, err := database.Begin(ctx)
	if err != nil {
		return false, err
	}
	// After a commit, the rollback does nothing.
	defer transaction.Rollback(ctx)

	var jobID int64
	err = transaction.QueryRow(ctx, `
		select id from jobs
		where finished_at is null
		order by id
		limit 1
		for update skip locked`).Scan(&jobID)
	if errors.Is(err, pgx.ErrNoRows) {
		return false, nil
	}
	if err != nil {
		return false, err
	}

	time.Sleep(time.Second) // the job's pretend work

	// clock_timestamp() is the time now; now() would be when the
	// transaction began.
	if _, err := transaction.Exec(ctx,
		"update jobs set finished_at = clock_timestamp(), finished_on_server = $2 where id = $1",
		jobID, hostName); err != nil {
		return false, err
	}
	if err := transaction.Commit(ctx); err != nil {
		return false, err
	}
	log.Printf("jobs: ran job %d", jobID)
	return true, nil
}

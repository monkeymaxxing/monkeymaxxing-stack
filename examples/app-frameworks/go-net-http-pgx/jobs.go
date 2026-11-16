package main

import (
	"context"
	"errors"
	"fmt"
	"log"
	"time"

	"github.com/jackc/pgx/v5"
	"github.com/jackc/pgx/v5/pgxpool"
)

func runJob(database *pgxpool.Pool) (bool, error) {
	ctx, cancel := context.WithTimeout(context.Background(), 10*time.Second)
	defer cancel()
	tx, err := database.Begin(ctx)
	if err != nil {
		return false, err
	}
	defer tx.Rollback(ctx)
	var id, owner, count int64
	err = tx.QueryRow(ctx, "select id,account_id from report_jobs where finished_at is null order by id limit 1 for update skip locked").Scan(&id, &owner)
	if errors.Is(err, pgx.ErrNoRows) {
		return false, nil
	}
	if err != nil {
		return false, err
	}
	if err = tx.QueryRow(ctx, "select count(*) from records where account_id=$1", owner).Scan(&count); err != nil {
		return false, err
	}
	if _, err = tx.Exec(ctx, "update report_jobs set output=$2,finished_at=clock_timestamp() where id=$1", id, fmt.Sprintf("record_count=%d\n", count)); err != nil {
		return false, err
	}
	return true, tx.Commit(ctx)
}
func worker(stop context.Context, database *pgxpool.Pool) error {
	for stop.Err() == nil {
		worked, err := runJob(database)
		if err != nil {
			log.Print("report job failed; unfinished work remains queued")
		}
		if !worked || err != nil {
			select {
			case <-stop.Done():
			case <-time.After(time.Second):
			}
		}
	}
	return nil
}

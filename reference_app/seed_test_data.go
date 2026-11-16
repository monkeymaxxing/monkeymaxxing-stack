package main

import (
	"context"
	"fmt"
	"log"
	"os"
	"time"
)

// seedTestData creates invented development or staging data after migrations.
func seedTestData() error {
	if os.Getenv("APP_ENV") != "development" && os.Getenv("APP_ENV") != "staging" {
		return fmt.Errorf("seed-test-data refuses to run: APP_ENV must be development or staging, so production never gets test data")
	}
	database, err := openDatabase()
	if err != nil {
		return err
	}
	defer database.Close()
	ctx, cancel := context.WithTimeout(context.Background(), 10*time.Second)
	defer cancel()
	_, err = database.Exec(ctx, `
		insert into page_views (app_server_host_name)
		select 'staging-seed'
		where not exists (select 1 from page_views where app_server_host_name = 'staging-seed');
		insert into jobs (added_on_server)
		select 'staging-seed'
		where not exists (select 1 from jobs where added_on_server = 'staging-seed')`)
	if err == nil {
		log.Print("seed-test-data: test page view and test job are present")
	}
	return err
}

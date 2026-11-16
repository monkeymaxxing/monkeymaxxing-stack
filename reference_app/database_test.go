package main

import (
	"context"
	"io"
	"net/http"
	"net/http/httptest"
	"os"
	"strings"
	"sync"
	"testing"
	"testing/fstest"

	"github.com/jackc/pgx/v5/pgxpool"
)

// testDatabase connects to the database in TEST_DATABASE_URL, a throwaway
// database whose tables the tests drop, and skips the test without one.
func testDatabase(t *testing.T) *pgxpool.Pool {
	databaseURL := os.Getenv("TEST_DATABASE_URL")
	if databaseURL == "" {
		t.Skip("TEST_DATABASE_URL names no throwaway database")
	}
	t.Setenv("DATABASE_URL", databaseURL)
	database, err := openDatabase()
	if err != nil {
		t.Fatal(err)
	}
	t.Cleanup(database.Close)
	if _, err := database.Exec(context.Background(),
		"drop table if exists schema_migrations, page_views, jobs"); err != nil {
		t.Fatal(err)
	}
	return database
}

func TestSeedTestDataRefusesUnsafeEnvironmentsBeforeOpeningDatabase(t *testing.T) {
	for _, appEnv := range []string{"production", "testing", ""} {
		t.Run("APP_ENV="+appEnv, func(t *testing.T) {
			t.Setenv("APP_ENV", appEnv)
			if appEnv == "" {
				os.Unsetenv("APP_ENV")
			}
			t.Setenv("DATABASE_URL", "not-a-database-url")
			err := seedTestData()
			want := "seed-test-data refuses to run: APP_ENV must be development or staging, so production never gets test data"
			if err == nil || err.Error() != want {
				t.Fatalf("seed refusal = %v; want %s", err, want)
			}
		})
	}
}

func TestSeedTestDataCreatesRowsWithoutDuplicatingThem(t *testing.T) {
	database := testDatabase(t)
	if err := migrate(); err != nil {
		t.Fatal(err)
	}
	for _, appEnv := range []string{"development", "staging"} {
		t.Setenv("APP_ENV", appEnv)
		if err := seedTestData(); err != nil {
			t.Fatal(err)
		}
	}
	var views, jobs int
	if err := database.QueryRow(context.Background(), `
		select (select count(*) from page_views where app_server_host_name = 'staging-seed'),
		       (select count(*) from jobs where added_on_server = 'staging-seed')`).Scan(&views, &jobs); err != nil {
		t.Fatal(err)
	}
	if views != 1 || jobs != 1 {
		t.Fatalf("after two seeds: %d test page views and %d test jobs; want one of each", views, jobs)
	}
}

func TestMigrationsApplyOnceEvenWhenTwoRunsStartAtOnce(t *testing.T) {
	database := testDatabase(t)
	ctx := context.Background()

	var runs sync.WaitGroup
	results := make(chan error, 2)
	for range 2 {
		runs.Go(func() { results <- migrate() })
	}
	runs.Wait()
	close(results)
	for err := range results {
		if err != nil {
			t.Fatal(err)
		}
	}

	var applied, appliedAt string
	if err := database.QueryRow(ctx,
		"select string_agg(version, ',' order by version), max(applied_at)::text from schema_migrations",
	).Scan(&applied, &appliedAt); err != nil {
		t.Fatal(err)
	}
	if want := "0001_create_page_views,0002_create_jobs"; applied != want {
		t.Errorf("schema_migrations lists %s, want %s", applied, want)
	}

	if err := migrate(); err != nil {
		t.Fatal(err)
	}
	var appliedAtAfterRerun string
	if err := database.QueryRow(ctx, "select max(applied_at)::text from schema_migrations").Scan(&appliedAtAfterRerun); err != nil {
		t.Fatal(err)
	}
	if appliedAtAfterRerun != appliedAt {
		t.Error("running migrate again changed schema_migrations")
	}
}

func TestTheHealthURLPassesOnlyOnceTheNewestMigrationIsApplied(t *testing.T) {
	database := testDatabase(t)
	handler := newWebHandler(database, database, "app001", fstest.MapFS{})
	askHealthURL := func() int {
		response := httptest.NewRecorder()
		handler.ServeHTTP(response, httptest.NewRequest(http.MethodGet, "/up", nil))
		return response.Code
	}

	if code := askHealthURL(); code != http.StatusServiceUnavailable {
		t.Errorf("before the migrations, /up answered %d", code)
	}
	if _, err := applyMigration(context.Background(), database, migrationVersions[0]); err != nil {
		t.Fatal(err)
	}
	if code := askHealthURL(); code != http.StatusServiceUnavailable {
		t.Errorf("with only %s applied, /up answered %d", migrationVersions[0], code)
	}
	if err := migrate(); err != nil {
		t.Fatal(err)
	}
	if code := askHealthURL(); code != http.StatusOK {
		t.Errorf("after the migrations, /up answered %d", code)
	}
}

func TestAJobRunsOnceAndRecordsItsServer(t *testing.T) {
	database := testDatabase(t)
	ctx := context.Background()
	if err := migrate(); err != nil {
		t.Fatal(err)
	}
	handler := newWebHandler(database, database, "app001", fstest.MapFS{})
	for range 2 {
		response := httptest.NewRecorder()
		handler.ServeHTTP(response, httptest.NewRequest(http.MethodPost, "/jobs", nil))
		if response.Code != http.StatusSeeOther {
			t.Fatalf("adding a job answered %d", response.Code)
		}
	}

	// Another worker holds the oldest job: this one takes the next.
	otherWorker, err := database.Begin(ctx)
	if err != nil {
		t.Fatal(err)
	}
	defer otherWorker.Rollback(ctx)
	if _, err := otherWorker.Exec(ctx, "select id from jobs order by id limit 1 for update"); err != nil {
		t.Fatal(err)
	}
	if ranAJob, err := runOneJob(database, "app002"); err != nil || !ranAJob {
		t.Fatalf("the worker ran no job (error: %v)", err)
	}
	if ranAJob, err := runOneJob(database, "app002"); err != nil || ranAJob {
		t.Fatalf("the worker ran a job that another worker holds (error: %v)", err)
	}

	var finishedOnServer string
	if err := database.QueryRow(ctx,
		"select string_agg(coalesce(finished_on_server, 'waiting'), ',' order by id) from jobs",
	).Scan(&finishedOnServer); err != nil {
		t.Fatal(err)
	}
	if want := "waiting,app002"; finishedOnServer != want {
		t.Errorf("the jobs' finished_on_server are %s, want %s", finishedOnServer, want)
	}
}

// A replica that restarts breaks the read pool's connection; the home page
// then counts on the primary's pool instead of failing, because the page
// view is already written.
func TestTheHomePageCountsOnThePrimaryWhenNoReplicaAnswers(t *testing.T) {
	database := testDatabase(t)
	if err := migrate(); err != nil {
		t.Fatal(err)
	}
	databaseForReads, err := pgxpool.New(context.Background(), databaseThatDoesNotAnswer)
	if err != nil {
		t.Fatal(err)
	}
	defer databaseForReads.Close()
	server := httptest.NewServer(newWebHandler(database, databaseForReads, "app001", fstest.MapFS{}))
	defer server.Close()

	response, err := http.Get(server.URL + "/")
	if err != nil {
		t.Fatal(err)
	}
	defer response.Body.Close()
	page, err := io.ReadAll(response.Body)
	if err != nil {
		t.Fatal(err)
	}
	if response.StatusCode != http.StatusOK {
		t.Fatalf("the home page answered %d, want 200: %s", response.StatusCode, page)
	}
	if !strings.Contains(string(page), "Page views so far") || !strings.Contains(string(page), ", the primary") {
		t.Errorf("the home page shows no count from the primary:\n%s", page)
	}
}

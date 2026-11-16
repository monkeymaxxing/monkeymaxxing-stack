package main

import (
	"context"
	"io"
	"net/http"
	"net/http/httptest"
	"strings"
	"testing"
	"testing/fstest"

	"github.com/jackc/pgx/v5/pgxpool"
)

// A database URL where no server answers: port 1 refuses connections.
const databaseThatDoesNotAnswer = "postgresql://reference_app@127.0.0.1:1/reference_app?connect_timeout=1"

func TestEveryAnswerSaysHowCloudflareMayCacheIt(t *testing.T) {
	database, err := pgxpool.New(context.Background(), databaseThatDoesNotAnswer)
	if err != nil {
		t.Fatal(err)
	}
	defer database.Close()
	assetFiles := fstest.MapFS{stylesheetFileName: {Data: stylesheet}}
	server := httptest.NewServer(newWebHandler(database, database, "app001", assetFiles))
	defer server.Close()

	tests := []struct {
		urlPath              string
		expectedStatusCode   int
		expectedCacheControl string
	}{
		// The home page never comes from Cloudflare's cache, even when the
		// database doesn't answer.
		{"/", http.StatusServiceUnavailable, "private, no-store"},
		{"/cached", http.StatusOK, "public, max-age=60"},
		// The health URL fails while the database doesn't answer.
		{"/up", http.StatusServiceUnavailable, "no-store"},
		{"/assets/" + stylesheetFileName, http.StatusOK, "public, max-age=31536000, immutable"},
		{"/assets/stylesheet-0000000000000000.css", http.StatusNotFound, "no-store"},
		{"/no-such-page", http.StatusNotFound, "no-store"},
	}
	for _, test := range tests {
		response, err := http.Get(server.URL + test.urlPath)
		if err != nil {
			t.Fatal(err)
		}
		response.Body.Close()
		if response.StatusCode != test.expectedStatusCode {
			t.Errorf("%s answered %d, want %d", test.urlPath, response.StatusCode, test.expectedStatusCode)
		}
		if cacheControl := response.Header.Get("Cache-Control"); cacheControl != test.expectedCacheControl {
			t.Errorf("%s answered Cache-Control %q, want %q", test.urlPath, cacheControl, test.expectedCacheControl)
		}
	}
}

func TestTheHomePageLinksThisReleasesStylesheet(t *testing.T) {
	database, err := pgxpool.New(context.Background(), databaseThatDoesNotAnswer)
	if err != nil {
		t.Fatal(err)
	}
	defer database.Close()
	server := httptest.NewServer(newWebHandler(database, database, "app001", fstest.MapFS{}))
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
	if link := `href="/assets/` + stylesheetFileName + `"`; !strings.Contains(string(page), link) {
		t.Errorf("the home page has no %s", link)
	}
}

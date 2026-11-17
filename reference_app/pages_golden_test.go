package main

import (
	"flag"
	"net/http/httptest"
	"os"
	"path/filepath"
	"regexp"
	"strings"
	"testing"
)

var updateGoldenFiles = flag.Bool("update-golden", false, "rewrite the files in testdata/ from the rendered pages")

// normalizeHTML makes two renderings of the same page comparable when they
// differ only in whitespace between tags or in the quoting of attributes:
// a template engine may write either.
func normalizeHTML(page string) string {
	whitespaceBetweenTags := regexp.MustCompile(`>\s+<`)
	page = whitespaceBetweenTags.ReplaceAllString(page, "><")
	page = strings.ReplaceAll(page, "&#34;", "&quot;")
	page = strings.ReplaceAll(page, "&#39;", "&apos;")
	return strings.TrimSpace(page)
}

func TestRenderedPagesMatchTheGoldenFiles(t *testing.T) {
	stylesheetPath := "/assets/stylesheet-0123456789abcdef.css"
	jobs := []jobRow{
		{ID: 12, Added: "2026-01-02 03:04:05 UTC on app001", Finished: "2026-01-02 03:04:09 UTC on app002"},
		{ID: 11, Added: "2026-01-02 03:00:00 UTC on app002", Finished: "not yet"},
	}
	pageViews := []pageViewRow{
		{ViewedAt: "2026-01-02 03:04:05 UTC", AppServerHostName: "app001", DatabaseServer: "10.20.2.1 (db01)"},
		{ViewedAt: "2026-01-02 03:04:01 UTC", AppServerHostName: "app002", DatabaseServer: "10.20.2.1 (db01)"},
	}
	tests := []struct {
		goldenFile string
		pageName   string
		statusCode int
		data       any
	}{
		{"home_with_rows.html", "home", 200, homePage{
			Release: "abc1234", StylesheetPath: stylesheetPath, AppServerHostName: "app001",
			RequestArrivedOn: "10.20.1.5 (app001)", DatabaseServer: "10.20.2.1 (db01)",
			PageViewCount: 42, CountedOn: "10.20.2.2 (db02), a replica", Jobs: jobs, PageViews: pageViews,
		}},
		{"home_with_empty_lists.html", "home", 200, homePage{
			Release: "abc1234", StylesheetPath: stylesheetPath, AppServerHostName: "app001",
			RequestArrivedOn: "none: the connection is through a Unix socket", DatabaseServer: "10.20.2.1 (db01)",
			PageViewCount: 1, CountedOn: "10.20.2.1 (db01), the primary",
		}},
		{"home_when_the_database_does_not_answer.html", "home", 503, homePage{
			Release: "abc1234", StylesheetPath: stylesheetPath, AppServerHostName: "app001",
			RequestArrivedOn: "10.20.1.5 (app001)",
			DatabaseProblem:  `recording the page view: dial tcp 127.0.0.1:1: connect: connection refused`,
		}},
		{"home_escapes_special_characters.html", "home", 503, homePage{
			Release: `r"1'<b>`, StylesheetPath: stylesheetPath, AppServerHostName: `<script>alert(1)</script>`,
			RequestArrivedOn: `a&b`, DatabaseProblem: `<img src=x onerror="alert('x')"> & more`,
			Jobs:      []jobRow{{ID: 1, Added: `<i>added</i>`, Finished: `"quoted"`}},
			PageViews: []pageViewRow{{ViewedAt: `<u>`, AppServerHostName: `'host'`, DatabaseServer: `a&b`}},
		}},
		{"cached.html", "cached", 200, cachedPage{
			Release: "abc1234", StylesheetPath: stylesheetPath, AppServerHostName: "app001",
			RenderedAt: "2026-01-02 03:04:05 UTC",
		}},
		{"cached_escapes_special_characters.html", "cached", 200, cachedPage{
			Release: `<b>`, StylesheetPath: stylesheetPath, AppServerHostName: `a&"b'`, RenderedAt: `<i>`,
		}},
	}
	for _, test := range tests {
		t.Run(test.goldenFile, func(t *testing.T) {
			recorder := httptest.NewRecorder()
			renderPageForGoldenTest(recorder, test.statusCode, test.pageName, test.data)
			if recorder.Code != test.statusCode {
				t.Errorf("status %d, want %d", recorder.Code, test.statusCode)
			}
			if contentType := recorder.Header().Get("Content-Type"); contentType != "text/html; charset=utf-8" {
				t.Errorf("Content-Type %q", contentType)
			}
			goldenPath := filepath.Join("testdata", test.goldenFile)
			if *updateGoldenFiles {
				if err := os.WriteFile(goldenPath, recorder.Body.Bytes(), 0o644); err != nil {
					t.Fatal(err)
				}
			}
			golden, err := os.ReadFile(goldenPath)
			if err != nil {
				t.Fatal(err)
			}
			if got, want := normalizeHTML(recorder.Body.String()), normalizeHTML(string(golden)); got != want {
				t.Errorf("rendered page differs from %s\n--- got\n%s\n--- want\n%s", goldenPath, got, want)
			}
		})
	}
}

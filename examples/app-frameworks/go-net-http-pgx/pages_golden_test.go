package main

import (
	"bytes"
	"flag"
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
	waiting := "Total records: 2\n<done> & \"ok\""
	tests := []struct {
		goldenFile string
		pageName   string
		data       pageData
	}{
		{"landing.html", "landing", pageData{}},
		{"portal_with_rows.html", "portal", pageData{
			Records:   []record{{ID: 1, Title: "Passport", Description: "Line one\nLine two"}, {ID: 2, Title: "Lease", Description: ""}},
			Documents: []document{{ID: 7, FileName: "scan.pdf", SHA256: "abc"}},
			Reports:   []report{{ID: 3, Output: &waiting}, {ID: 4, Output: nil}},
		}},
		{"portal_with_empty_lists.html", "portal", pageData{Records: []record{}}},
		{"portal_escapes_customer_input.html", "portal", pageData{
			Records:   []record{{ID: 1, Title: `"><script>alert(1)</script>`, Description: "</textarea><script>alert(2)</script>"}},
			Documents: []document{{ID: 2, FileName: `<img src=x onerror=alert(3)>.pdf`, SHA256: "abc"}},
			Reports:   []report{{ID: 5, Output: func() *string { s := "</pre><script>alert(4)</script>"; return &s }()}},
		}},
	}
	for _, test := range tests {
		t.Run(test.goldenFile, func(t *testing.T) {
			var output bytes.Buffer
			if err := renderPageForGoldenTest(&output, test.pageName, test.data); err != nil {
				t.Fatal(err)
			}
			goldenPath := filepath.Join("testdata", test.goldenFile)
			if *updateGoldenFiles {
				if err := os.WriteFile(goldenPath, output.Bytes(), 0o644); err != nil {
					t.Fatal(err)
				}
			}
			golden, err := os.ReadFile(goldenPath)
			if err != nil {
				t.Fatal(err)
			}
			if got, want := normalizeHTML(output.String()), normalizeHTML(string(golden)); got != want {
				t.Errorf("rendered page differs from %s\n--- got\n%s\n--- want\n%s", goldenPath, got, want)
			}
		})
	}
}

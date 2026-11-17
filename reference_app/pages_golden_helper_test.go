package main

import "net/http"

// renderPageForGoldenTest is the one place the golden test calls the page
// renderer.
func renderPageForGoldenTest(w http.ResponseWriter, status int, pageName string, data any) {
	render(w, status, pageName, data)
}

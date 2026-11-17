package main

import (
	"context"
	"io"
)

// renderPageForGoldenTest is the one place the golden test calls the page
// renderer. The landing page takes no data.
func renderPageForGoldenTest(w io.Writer, pageName string, data pageData) error {
	if pageName == "landing" {
		return landingPage().Render(context.Background(), w)
	}
	return portalPage(data).Render(context.Background(), w)
}

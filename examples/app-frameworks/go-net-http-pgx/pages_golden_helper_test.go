package main

import "io"

// renderPageForGoldenTest is the one place the golden test calls the page
// renderer. The landing page takes no data.
func renderPageForGoldenTest(w io.Writer, pageName string, data pageData) error {
	if pageName == "landing" {
		return pages.ExecuteTemplate(w, pageName, nil)
	}
	return pages.ExecuteTemplate(w, pageName, data)
}

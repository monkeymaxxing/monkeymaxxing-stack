package main

import (
	"crypto/sha256"
	_ "embed"
	"fmt"
	"log"
	"os"
	"path/filepath"
)

// assetDirectory holds the asset files that the web server serves under
// /assets/: the directory assets in the program's working directory, which
// is /app/assets in the image and the app's asset_directory in the systems
// repository. On the stack, a directory that holds this release's and the
// previous release's files is mounted over it, so a page the previous
// release rendered still finds its stylesheet after a deploy.
const assetDirectory = "assets"

//go:embed stylesheet.css
var stylesheet []byte

// stylesheetFileName is the stylesheet's file name with a fingerprint of
// its content, such as stylesheet-3f2a9c0e1b7d4a6f.css. Each version of the
// stylesheet has its own name, so two releases' files sit side by side in
// the asset directory, and a browser or Cloudflare may keep each file for
// as long as it likes.
var stylesheetFileName = fingerprintedFileName("stylesheet", ".css", stylesheet)

// fingerprintedFileName returns name, the first 16 hexadecimal digits of the
// SHA-256 of content, and extension, such as stylesheet-3f2a9c0e1b7d4a6f.css.
func fingerprintedFileName(name, extension string, content []byte) string {
	sum := sha256.Sum256(content)
	return fmt.Sprintf("%s-%x%s", name, sum[:8], extension)
}

// writeAssets writes the asset files into the asset directory under their
// fingerprinted names. The Containerfile runs it when it builds the image.
func writeAssets() error {
	if err := os.MkdirAll(assetDirectory, 0o755); err != nil {
		return err
	}
	filePath := filepath.Join(assetDirectory, stylesheetFileName)
	if err := os.WriteFile(filePath, stylesheet, 0o644); err != nil {
		return err
	}
	log.Printf("write-assets: wrote %s", filePath)
	return nil
}

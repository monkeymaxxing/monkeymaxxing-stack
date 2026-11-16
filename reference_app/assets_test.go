package main

import (
	"bytes"
	"os"
	"path/filepath"
	"strings"
	"testing"
)

func TestWriteAssetsWritesTheStylesheetUnderTheNameThePageLinks(t *testing.T) {
	t.Chdir(t.TempDir())
	if err := writeAssets(); err != nil {
		t.Fatal(err)
	}
	written, err := os.ReadFile(filepath.Join(assetDirectory, stylesheetFileName))
	if err != nil {
		t.Fatal(err)
	}
	if !bytes.Equal(written, stylesheet) {
		t.Error("the written file isn't the stylesheet")
	}
}

func TestTheFingerprintFollowsTheContent(t *testing.T) {
	first := fingerprintedFileName("stylesheet", ".css", []byte("body { color: black; }"))
	again := fingerprintedFileName("stylesheet", ".css", []byte("body { color: black; }"))
	changed := fingerprintedFileName("stylesheet", ".css", []byte("body { color: navy; }"))
	if first != again {
		t.Errorf("the same content got two names: %s and %s", first, again)
	}
	if first == changed {
		t.Errorf("changed content kept the name %s", first)
	}
	if !strings.HasPrefix(first, "stylesheet-") || !strings.HasSuffix(first, ".css") {
		t.Errorf("%s doesn't keep the name and extension", first)
	}
}

package main

import (
	"bytes"
	"net/http"
	"net/http/httptest"
	"net/url"
	"strings"
	"testing"
	"time"
)

func TestBrowserWriteOrigin(t *testing.T) {
	handler := (&app{origin: "https://portal.example.com"}).routes()
	for _, origin := range []string{"", "https://evil.example.com", "null"} {
		request := httptest.NewRequest("POST", "/logout", nil)
		request.Header.Set("Origin", origin)
		result := httptest.NewRecorder()
		handler.ServeHTTP(result, request)
		if result.Code != 403 {
			t.Fatalf("origin %q: got %d", origin, result.Code)
		}
	}
	request := httptest.NewRequest("POST", "/logout", nil)
	request.Header.Set("Origin", "https://portal.example.com")
	request.Header.Set("Accept", "application/json")
	result := httptest.NewRecorder()
	handler.ServeHTTP(result, request)
	if result.Code != 200 {
		t.Fatalf("same origin logout: %d", result.Code)
	}
	cookie := result.Result().Cookies()[0]
	if !cookie.Secure || !cookie.HttpOnly || cookie.Path != "/" || cookie.SameSite != http.SameSiteLaxMode || cookie.MaxAge != -1 {
		t.Fatal("session cookie flags are unsafe")
	}
}
func TestUnauthenticatedReadsAndWrites(t *testing.T) {
	handler := (&app{origin: "https://portal.example.com"}).routes()
	for _, endpoint := range []string{"/records", "/documents", "/reports", "/documents/1"} {
		result := httptest.NewRecorder()
		handler.ServeHTTP(result, httptest.NewRequest("GET", endpoint, nil))
		if result.Code != 401 {
			t.Fatalf("%s: %d", endpoint, result.Code)
		}
	}
}
func TestCredentialAndRecordValidation(t *testing.T) {
	for _, password := range []string{"short", strings.Repeat("x", 73)} {
		form := url.Values{"email": {"barbara@example.com"}, "password": {password}}
		request := httptest.NewRequest("POST", "/login", strings.NewReader(form.Encode()))
		request.Header.Set("Content-Type", "application/x-www-form-urlencoded")
		if _, _, err := credentialsForm(request); err == nil {
			t.Fatal("invalid password accepted")
		}
	}
	for _, title := range []string{" ", strings.Repeat("x", 201)} {
		request := httptest.NewRequest("POST", "/records", strings.NewReader(url.Values{"title": {title}}.Encode()))
		request.Header.Set("Content-Type", "application/x-www-form-urlencoded")
		if _, _, valid := recordForm(request); valid {
			t.Fatal("invalid record accepted")
		}
	}
}
func TestTemplateEscapesCustomerInput(t *testing.T) {
	var output bytes.Buffer
	err := pages.ExecuteTemplate(&output, "portal", pageData{Records: []record{{ID: 1, Title: "<script>alert(1)</script>", Description: "</textarea><script>"}}})
	if err != nil {
		t.Fatal(err)
	}
	if strings.Contains(output.String(), "<script>") {
		t.Fatal("customer HTML was not escaped")
	}
}
func TestDatabaseUsesMultipleHostsAndHostKeepalive(t *testing.T) {
	config, err := databaseConfig("postgresql://portal:invented@db01:5432,db02:5432/portal?target_session_attrs=read-write&connect_timeout=3")
	if err != nil {
		t.Fatal(err)
	}
	if config.ConnConfig.Host != "db01" || len(config.ConnConfig.Fallbacks) == 0 || config.ConnConfig.ValidateConnect == nil || config.ConnConfig.DialFunc == nil || config.ConnConfig.ConnectTimeout != 3*time.Second {
		t.Fatal("multi-host primary connection configuration missing")
	}
}

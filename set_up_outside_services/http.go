package main

import (
	"bytes"
	"encoding/json"
	"fmt"
	"io"
	"net/http"
	"time"
)

// httpClient is shared by the providers' clients. It uses the system's
// certificate authorities and a time limit, so a stalled request fails with
// a message instead of waiting forever.
var httpClient = &http.Client{Timeout: 60 * time.Second}

// apiError is a provider's refusal, holding only the HTTP status and the
// provider's own error code. It never holds a request, a response body, or
// the provider's message: each can repeat what the request sent, such as a
// key, and the coding agent reads every error. The status and the code are
// enough to look the refusal up in the provider's documentation.
type apiError struct {
	Provider string
	Call     string
	Status   int
	Code     string
}

func (e *apiError) Error() string {
	if e.Code == "" {
		return fmt.Sprintf("%s refused %s with HTTP %d", e.Provider, e.Call, e.Status)
	}
	return fmt.Sprintf("%s refused %s with HTTP %d, code %s", e.Provider, e.Call, e.Status, e.Code)
}

// networkError says a request may or may not have reached the provider.
type networkError struct {
	Provider string
	Call     string
	Err      error
}

func (e *networkError) Error() string {
	return fmt.Sprintf("the request to %s (%s) did not complete: %v", e.Provider, e.Call, e.Err)
}

// doJSON sends one request with a JSON body, or none, and decodes a JSON
// answer into result. readError turns a refusal's body into a code; its
// second answer, the provider's message, is never kept.
func doJSON(provider, call, method, url string, headers map[string]string, body any, result any, readError func([]byte) (string, string)) (int, error) {
	var reader io.Reader
	if body != nil {
		encoded, err := json.Marshal(body)
		if err != nil {
			return 0, err
		}
		reader = bytes.NewReader(encoded)
	}
	request, err := http.NewRequest(method, url, reader)
	if err != nil {
		return 0, err
	}
	if body != nil {
		request.Header.Set("Content-Type", "application/json")
	}
	for name, value := range headers {
		request.Header.Set(name, value)
	}
	response, err := httpClient.Do(request)
	if err != nil {
		return 0, &networkError{Provider: provider, Call: call, Err: stripURLFromError(err)}
	}
	defer response.Body.Close()
	answer, err := io.ReadAll(io.LimitReader(response.Body, 8<<20))
	if err != nil {
		return response.StatusCode, &networkError{Provider: provider, Call: call, Err: err}
	}
	if response.StatusCode < 200 || response.StatusCode > 299 {
		code, _ := readError(answer)
		return response.StatusCode, &apiError{Provider: provider, Call: call, Status: response.StatusCode, Code: code}
	}
	if result != nil {
		if err := json.Unmarshal(answer, result); err != nil {
			return response.StatusCode, fmt.Errorf("%s answered %s with something this command cannot read", provider, call)
		}
	}
	return response.StatusCode, nil
}

// stripURLFromError keeps Go's url.Error from repeating the request's
// address. No secret goes in an address, but a short message reads better.
func stripURLFromError(err error) error {
	type unwrapper interface{ Unwrap() error }
	if wrapped, ok := err.(unwrapper); ok && wrapped.Unwrap() != nil {
		return wrapped.Unwrap()
	}
	return err
}

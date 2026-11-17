// serve runs the stand-ins for the desk test on a disposable server: B2 at
// api.backblazeb2.com, Cloudflare at api.cloudflare.com, and a bearer-token
// server provider at api.hetzner.cloud, all on one TLS address that the
// test's /etc/hosts points those names at. standins.test answers the test
// harness: GET /state, POST /fail, POST /add-token, POST /ignore-locks.
// It is test equipment, never part of a release.
package main

import (
	"crypto/tls"
	"encoding/json"
	"flag"
	"log"
	"net/http"
	"os"
	"strings"
	"sync"

	"github.com/monkeymaxxing/monkeymaxxing-stack/set_up_outside_services/internal/standins"
)

func main() {
	address := flag.String("address", "127.0.0.1:443", "")
	certificate := flag.String("certificate", "", "")
	key := flag.String("key", "", "")
	// The synthetic credentials come from the environment, never arguments,
	// so the desk test can show that no credential is in the process list.
	masterKeyID, masterKey := os.Getenv("STANDIN_B2_MASTER_KEY_ID"), os.Getenv("STANDIN_B2_MASTER_KEY")
	accountID := flag.String("cloudflare-account-id", "", "")
	zone := flag.String("cloudflare-zone", "example.org", "")
	zoneStatus := flag.String("cloudflare-zone-status", "active", "active, pending before the domain moved, or absent before go-live adds it")
	providerToken := os.Getenv("STANDIN_PROVIDER_TOKEN")
	flag.Parse()

	b2 := standins.NewB2(masterKeyID, masterKey)
	b2.BaseURL = "https://api.backblazeb2.com"
	cloudflare := standins.NewCloudflare(*accountID)
	cloudflare.ZoneName = *zone
	cloudflare.ZoneStatus = strings.TrimPrefix(*zoneStatus, "absent")
	var providerTokens = map[string]bool{providerToken: true}
	// The provider's registered SSH keys, as Hetzner Cloud's API lists them.
	var providerSSHKeys []map[string]any
	var providerMutex sync.Mutex

	admin := http.NewServeMux()
	admin.HandleFunc("GET /state", func(w http.ResponseWriter, r *http.Request) {
		_ = json.NewEncoder(w).Encode(map[string]any{"b2": b2.Snapshot(), "cloudflare": cloudflare.Snapshot()})
	})
	admin.HandleFunc("POST /fail", func(w http.ResponseWriter, r *http.Request) {
		var body struct{ Provider, Call, Mode string }
		if json.NewDecoder(r.Body).Decode(&body) != nil {
			http.Error(w, "bad body", 400)
			return
		}
		if body.Provider == "b2" {
			b2.Lock()
			b2.Failures[body.Call] = body.Mode
			b2.Unlock()
		} else {
			cloudflare.Lock()
			cloudflare.Failures[body.Call] = body.Mode
			cloudflare.Unlock()
		}
	})
	admin.HandleFunc("POST /add-token", func(w http.ResponseWriter, r *http.Request) {
		var body struct {
			Provider, Name, Value string
			UserOwned             bool `json:"user_owned"`
			Permissions           []string
		}
		if json.NewDecoder(r.Body).Decode(&body) != nil {
			http.Error(w, "bad body", 400)
			return
		}
		if body.Provider == "server-provider" {
			providerTokens[body.Value] = true
			return
		}
		cloudflare.AddToken(body.Name, body.Value, body.UserOwned, body.Permissions...)
	})
	admin.HandleFunc("POST /add-b2-key", func(w http.ResponseWriter, r *http.Request) {
		var key standins.B2Key
		if json.NewDecoder(r.Body).Decode(&key) != nil {
			http.Error(w, "bad body", 400)
			return
		}
		b2.Lock()
		b2.Keys = append(b2.Keys, &key)
		b2.Unlock()
	})
	admin.HandleFunc("POST /ignore-locks", func(w http.ResponseWriter, r *http.Request) {
		b2.Lock()
		b2.IgnoreLocks = r.URL.Query().Get("value") == "true"
		b2.Unlock()
	})
	provider := http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
		if !providerTokens[strings.TrimPrefix(r.Header.Get("Authorization"), "Bearer ")] {
			w.WriteHeader(http.StatusUnauthorized)
			_, _ = w.Write([]byte(`{"error": {"code": "unauthorized", "message": "unable to authenticate"}}`))
			return
		}
		providerMutex.Lock()
		defer providerMutex.Unlock()
		// https://docs.hetzner.cloud/reference/cloud#ssh-keys
		switch {
		case r.URL.Path == "/v1/servers" && r.Method == http.MethodGet:
			_, _ = w.Write([]byte(`{"servers": [{"id": 1, "name": "desk01"}]}`))
		case r.URL.Path == "/v1/ssh_keys" && r.Method == http.MethodGet:
			_ = json.NewEncoder(w).Encode(map[string]any{"ssh_keys": append([]map[string]any{}, providerSSHKeys...)})
		case r.URL.Path == "/v1/ssh_keys" && r.Method == http.MethodPost:
			var body struct {
				Name      string `json:"name"`
				PublicKey string `json:"public_key"`
			}
			if json.NewDecoder(r.Body).Decode(&body) != nil || body.Name == "" || !strings.HasPrefix(body.PublicKey, "ssh-") {
				w.WriteHeader(http.StatusBadRequest)
				_, _ = w.Write([]byte(`{"error": {"code": "invalid_input", "message": "name and public_key are required"}}`))
				return
			}
			key := map[string]any{"id": len(providerSSHKeys) + 1, "name": body.Name, "public_key": body.PublicKey}
			providerSSHKeys = append(providerSSHKeys, key)
			w.WriteHeader(http.StatusCreated)
			_ = json.NewEncoder(w).Encode(map[string]any{"ssh_key": key})
		default:
			w.WriteHeader(http.StatusNotFound)
		}
	})
	handler := http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
		host := strings.Split(r.Host, ":")[0]
		log.Printf("%s %s %s", host, r.Method, r.URL.Path)
		switch host {
		case "api.backblazeb2.com":
			b2.ServeHTTP(w, r)
		case "api.cloudflare.com":
			cloudflare.ServeHTTP(w, r)
		case "api.hetzner.cloud":
			provider.ServeHTTP(w, r)
		case "standins.test":
			admin.ServeHTTP(w, r)
		default:
			http.Error(w, "unknown host "+host, http.StatusMisdirectedRequest)
		}
	})
	// HTTP/1.1 only: a stand-in that drops an answer hijacks the connection,
	// which HTTP/2 does not allow.
	server := &http.Server{Addr: *address, Handler: handler, TLSNextProto: map[string]func(*http.Server, *tls.Conn, http.Handler){}}
	log.Fatal(server.ListenAndServeTLS(*certificate, *key))
}

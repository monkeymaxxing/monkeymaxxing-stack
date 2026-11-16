package main

import (
	"os"
	"path/filepath"
	"strings"
	"testing"
)

// codexHarness makes mmx_project_settings.yml name Codex as the triage
// agent's coding agent, and leaves only the triage credential for the step
// to ask.
func codexHarness(t *testing.T) *harness {
	h := newHarness(t, false, false)
	h.setTriageAgentCodingAgent(t, "codex")
	h.commitAll("Use Codex")
	h.vault.referenced = []string{"mmhotline_triage_agent_credential"}
	h.signedSecretsRepository()
	return h
}

func TestSecretsCodexOffersThreeCredentialTypesAndGivesEachSource(t *testing.T) {
	for _, test := range []struct {
		answer, credentialType, source string
	}{
		{"key", "api_key", "https://platform.openai.com/api-keys"},
		{"token", "access_token", "Access tokens page"},
		{"sign-in", "chatgpt_sign_in", "codex login"},
	} {
		h := codexHarness(t)
		visible := []string{test.answer}
		hidden := []string{"credential-value"}
		switch test.credentialType {
		case "access_token":
			visible = append(visible, "2999-02-06")
		case "chatgpt_sign_in":
			path := filepath.Join(t.TempDir(), "auth.json")
			writeFile(t, path, "{\"tokens\": {\"access_token\": \"quote\\\" and\\nnewline\"}}\n")
			visible = append(visible, path)
			hidden = nil
		}
		h.answerSecrets(hidden, visible)
		if err := runSecrets(h.e, nil); err != nil {
			t.Fatalf("%s: %v\n%s", test.answer, err, h.out)
		}
		out := h.out.String()
		if !strings.Contains(out, "Codex accepts three kinds of credential") || !strings.Contains(out, test.source) ||
			!strings.Contains(out, "credential_type: "+test.credentialType) {
			t.Errorf("%s: the output lacks the Codex menu, %q, or credential_type %s:\n%s", test.answer, test.source, test.credentialType, out)
		}
		if test.credentialType == "access_token" && !strings.Contains(out, `credential_expires_on: "2999-02-06"`) {
			t.Errorf("the output does not tell the coding agent the end date:\n%s", out)
		}
		if test.credentialType != "access_token" && strings.Contains(out, "credential_expires_on") {
			t.Errorf("%s: the output names an end date:\n%s", test.answer, out)
		}
		if h.vault.values["mmhotline_triage_agent_credential"] == "" {
			t.Errorf("%s: nothing was saved", test.answer)
		}
		h.requireNoSecretInOutput()
	}
}

func TestSecretsAccessTokenEndDateMustBeAFutureDate(t *testing.T) {
	h := codexHarness(t)
	h.answerSecrets([]string{"token-value"}, []string{"token", "February 6", "2020-01-01", "2999-02-06"})
	if err := runSecrets(h.e, nil); err != nil {
		t.Fatal(err)
	}
	out := h.out.String()
	if !strings.Contains(out, "Write the date as YYYY-MM-DD") || !strings.Contains(out, "That date has passed") ||
		!strings.Contains(out, `credential_expires_on: "2999-02-06"`) {
		t.Errorf("the date was not checked:\n%s", out)
	}
}

func TestSecretsChatGPTSignInSavesTheFileUnchangedAndChecksIt(t *testing.T) {
	good := "{\n  \"auth_mode\": \"chatgpt\",\n  \"note\": \"a \\\"quoted\\\" word\"\n}\n"
	directory := t.TempDir()
	notJSON := filepath.Join(directory, "not_json")
	writeFile(t, notJSON, "this is not json")
	tooLong := filepath.Join(directory, "too_long.json")
	writeFile(t, tooLong, `{"a": "`+strings.Repeat("x", 64*1024)+`"}`)
	goodPath := filepath.Join(directory, "auth.json")
	writeFile(t, goodPath, good)
	h := codexHarness(t)
	h.answerSecrets(nil, []string{"sign-in", filepath.Join(directory, "missing"), notJSON, tooLong, goodPath})
	if err := runSecrets(h.e, nil); err != nil {
		t.Fatal(err)
	}
	if h.vault.values["mmhotline_triage_agent_credential"] != good {
		t.Errorf("the sign-in was not saved unchanged: %q", h.vault.values["mmhotline_triage_agent_credential"])
	}
	out := h.out.String()
	for _, want := range []string{"I could not read", "not valid JSON", "longer than 64 KiB", "never run codex logout", "no connected apps"} {
		if !strings.Contains(out, want) {
			t.Errorf("the output lacks %q:\n%s", want, out)
		}
	}
	if strings.Contains(out, "auth_mode") {
		t.Errorf("the output shows the file's content:\n%s", out)
	}
}

func TestSecretsAsksWhichCodingAgentWhenTheSettingsDoNotSay(t *testing.T) {
	h := newHarness(t, false, false)
	h.setTriageAgentCodingAgent(t, "")
	h.commitAll("Remove the coding agent setting")
	h.vault.referenced = []string{"mmhotline_triage_agent_credential"}
	h.signedSecretsRepository()
	h.answerSecrets([]string{"openai-key-value"}, []string{"codex", "key"})
	if err := runSecrets(h.e, nil); err != nil {
		t.Fatal(err)
	}
	if out := h.out.String(); !strings.Contains(out, "Codex accepts three kinds") || !strings.Contains(out, "platform.openai.com/api-keys") {
		t.Errorf("the Codex menu did not follow the answer:\n%s", out)
	}
}

// setTriageAgentCodingAgent writes value as triage_agent_coding_agent in
// mmx_project_settings.yml, or removes the setting when value is "".
func (h *harness) setTriageAgentCodingAgent(t *testing.T, value string) {
	t.Helper()
	path := filepath.Join(h.e.directory, projectSettingsFile)
	text, err := os.ReadFile(path)
	if err != nil {
		t.Fatal(err)
	}
	line := "  triage_agent_coding_agent: claude_code\n"
	if !strings.Contains(string(text), line) {
		t.Fatalf("%s lacks %q", projectSettingsFile, line)
	}
	replacement := ""
	if value != "" {
		replacement = "  triage_agent_coding_agent: " + value + "\n"
	}
	writeFile(t, path, strings.Replace(string(text), line, replacement, 1))
}

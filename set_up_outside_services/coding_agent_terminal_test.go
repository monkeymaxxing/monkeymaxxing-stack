package main

import (
	"encoding/json"
	"os"
	"path/filepath"
	"testing"
)

// The coding agent's Git runs with the person's command still on the
// terminal, where the person types secrets. A coding-agent process that held
// that terminal could read what is typed or repaint the screen, so
// gitAsTheCodingAgent gives it no terminal: no terminal on standard input,
// output or error, and a session of its own, which has no controlling
// terminal, so /dev/tty does not open either.
func TestTheCodingAgentsGitGetsNoTerminal(t *testing.T) {
	directory := t.TempDir()
	report := filepath.Join(directory, "report.json")
	standIn := filepath.Join(directory, "sudo")
	writeFile(t, standIn, `#!/usr/bin/env python3
import json, os
json.dump({"terminal_on": [n for n in (0, 1, 2) if os.isatty(n)], "session_leader": os.getsid(0) == os.getpid()},
          open(`+"'"+report+"'"+`, "w"))
`)
	if err := os.Chmod(standIn, 0o755); err != nil {
		t.Fatal(err)
	}
	original := sudoProgram
	sudoProgram = standIn
	defer func() { sudoProgram = original }()
	if _, err := gitAsTheCodingAgent(directory)("status"); err != nil {
		t.Fatal(err)
	}
	text, err := os.ReadFile(report)
	if err != nil {
		t.Fatal(err)
	}
	var found struct {
		TerminalOn    []int `json:"terminal_on"`
		SessionLeader bool  `json:"session_leader"`
	}
	if err := json.Unmarshal(text, &found); err != nil {
		t.Fatal(err)
	}
	if len(found.TerminalOn) != 0 || !found.SessionLeader {
		t.Fatalf("the coding agent's Git got a terminal on %v, or shares the person's session (session leader: %v)", found.TerminalOn, found.SessionLeader)
	}
}

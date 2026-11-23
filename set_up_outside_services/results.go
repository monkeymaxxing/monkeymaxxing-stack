package main

import (
	"bytes"
	"encoding/json"
	"errors"
	"fmt"
	"os"
	"os/exec"
	"time"
)

// The results file tells the coding agent what each account command did,
// also after a run in the person's own window, whose screen the agent never
// sees. Every command reads it, changes its own step and notes, and writes
// it back, so the commands of one setup add up in one file. It holds step
// names, their states, and values that are not secrets, never a secret.
const setupResultsFile = "/var/lib/monkeymaxxing-stack/setup_results.json"

// The states of a step in the results file.
const (
	stepInProgress = "in_progress"
	stepDone       = "done"
	// stepNotNeeded: the step has nothing to do on this system.
	stepNotNeeded = "not_needed"
)

type stepResult struct {
	Name  string `json:"name"`
	State string `json:"state"`
}

// setupResults is the results file's content.
type setupResults struct {
	// Command is the command that wrote the file last.
	Command   string       `json:"command"`
	Version   string       `json:"version"`
	UpdatedAt string       `json:"updated_at"`
	Steps     []stepResult `json:"steps"`
	// Finished is set by lock-the-desk, the setup's last command.
	Finished bool `json:"finished"`
	// StoppedWith is the reason the last run stopped. Error messages hold no
	// secret: a provider's refusal keeps only its status and code.
	StoppedWith string `json:"stopped_with,omitempty"`
	// ForTheCodingAgent holds values that are not secrets: settings the
	// coding agent writes, such as cloudflare_account_id, and facts it
	// checks, such as the domain's nameservers.
	ForTheCodingAgent map[string]string `json:"for_the_coding_agent"`
}

func (r setupResults) state(name string) string {
	for _, step := range r.Steps {
		if step.Name == name {
			return step.State
		}
	}
	return ""
}

func (r *setupResults) setState(name, state string) {
	for i := range r.Steps {
		if r.Steps[i].Name == name {
			r.Steps[i].State = state
			return
		}
	}
	r.Steps = append(r.Steps, stepResult{Name: name, State: state})
}

// readResults reads the results file. A missing or unreadable file reads as
// empty: every step not started.
func (e *environment) readResults() setupResults {
	var results setupResults
	if text, err := os.ReadFile(e.resultsFile); err == nil {
		_ = json.Unmarshal(text, &results)
	}
	if results.ForTheCodingAgent == nil {
		results.ForTheCodingAgent = map[string]string{}
	}
	return results
}

// updateResults reads the results file, changes it, and writes it back.
func (e *environment) updateResults(change func(*setupResults)) error {
	results := e.readResults()
	change(&results)
	results.Command, results.Version = e.commandLine, version
	results.UpdatedAt = e.now().UTC().Format(time.RFC3339)
	content, err := json.MarshalIndent(results, "", "  ")
	if err != nil {
		return err
	}
	// The results file is readable by everyone, so the coding agent reads it
	// and cannot change it.
	if err := e.writeFileAsRoot(e.resultsFile, 0o644, append(content, '\n')); err != nil {
		return fmt.Errorf("writing the results file %s failed: %v", e.resultsFile, err)
	}
	return nil
}

// asStep runs one command's work as the step name of the results file: in
// progress while it runs, then the state work returns, or the reason it
// stopped in stopped_with. notes go to for_the_coding_agent either way, so a
// stop can name what the coding agent needs, such as the Backblaze account's
// region. An empty name records no step's state, for a command such as
// secrets that saves several keys, each recorded as its own step.
func (e *environment) asStep(name string, work func(notes map[string]string) (string, error)) error {
	err := e.updateResults(func(r *setupResults) {
		// The coding agent reads stopped_with for the last run, so a new run
		// drops an earlier run's reason.
		r.StoppedWith = ""
		if name != "" {
			r.setState(name, stepInProgress)
		}
	})
	if err != nil {
		return err
	}
	notes := map[string]string{}
	state, err := work(notes)
	addNotes := func(r *setupResults) {
		for key, value := range notes {
			r.ForTheCodingAgent[key] = value
		}
	}
	if err != nil {
		_ = e.updateResults(func(r *setupResults) { addNotes(r); r.StoppedWith = trimPeriod(err.Error()) })
		return err
	}
	return e.updateResults(func(r *setupResults) {
		addNotes(r)
		if name != "" {
			r.setState(name, state)
		}
	})
}

// writeFileAsRootWithSudo writes a file only root may change, such as the
// results file or the kept backup key, with mode. The content goes on
// standard input, never in an argument. The file is made with umask 077 and
// then given its mode, so a secret is never readable by another account,
// while a new folder above it gets umask 022, so everyone can reach the
// results file.
func writeFileAsRootWithSudo(path string, mode os.FileMode, content []byte) error {
	script := `set -e; umask 022; mkdir -p "${1%/*}"; umask 077; cat > "$1.new"; chmod "$2" "$1.new"; mv "$1.new" "$1"`
	command := exec.Command("sudo", "-n", "sh", "-c", script, "sh", path, fmt.Sprintf("%04o", mode))
	command.Stdin = bytes.NewReader(content)
	if output, err := command.CombinedOutput(); err != nil {
		return errors.New(firstLine(string(output), err))
	}
	return nil
}

// removeFileAsRootWithSudo deletes a file only root may change.
func removeFileAsRootWithSudo(path string) error {
	if output, err := exec.Command("sudo", "-n", "rm", "-f", "--", path).CombinedOutput(); err != nil {
		return errors.New(firstLine(string(output), err))
	}
	return nil
}

// readRootFileWithSudo reads a file only root reads, such as the API proxy's
// token file. The content never shows on the screen.
func readRootFileWithSudo(path string) ([]byte, error) {
	command := exec.Command("sudo", "-n", "cat", "--", path)
	var output, errorOutput bytes.Buffer
	command.Stdout, command.Stderr = &output, &errorOutput
	if err := command.Run(); err != nil {
		return nil, errors.New(firstLine(errorOutput.String(), err))
	}
	return output.Bytes(), nil
}

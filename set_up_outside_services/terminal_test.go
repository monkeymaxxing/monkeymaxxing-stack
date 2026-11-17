package main

import (
	"os"
	"os/exec"
	"strings"
	"testing"
	"time"
)

// The questions run in a real terminal: python3's pty module makes one, and
// the test binary runs itself as the program under test inside it.

// questionsHelper is the program inside the terminal. It waits, so keys
// typed ahead are queued, asks a hidden question, a yes/no question that the
// terminal ends with Ctrl-D (no answer, so the line stays open), then a
// hidden question again.
func TestQuestionsHelperProcess(t *testing.T) {
	if os.Getenv("QUESTIONS_HELPER") != "1" {
		t.Skip("runs only inside the terminal that TestQuestionsInARealTerminal makes")
	}
	os.Stdout.WriteString("READY\n")
	<-waitForTheTypedAheadKeys
	first, err := readHiddenLine("First token (hidden): ")
	os.Stdout.WriteString("GOT-FIRST=" + first + " ERR=" + errText(err) + "\n")
	_, err = readVisibleLine("Use it (yes)? ")
	os.Stdout.WriteString("GOT-VISIBLE ERR=" + errText(err) + "\n")
	second, err := readHiddenLine("Second token (hidden): ")
	os.Stdout.WriteString("GOT-SECOND=" + second + " ERR=" + errText(err) + "\n")
}

// waitForTheTypedAheadKeys: the driver types ahead right after READY.
var waitForTheTypedAheadKeys = time.After(700 * time.Millisecond)

const driver = `
import os, pty, sys, time, select
pid, fd = pty.fork()
if pid == 0:
    os.execv(sys.argv[1], [sys.argv[1], '-test.run=TestQuestionsHelperProcess', '-test.v'])
def read_until(text, seconds=15):
    data = b''
    end = time.time() + seconds
    while text not in data and time.time() < end:
        if select.select([fd], [], [], 0.2)[0]:
            try:
                chunk = os.read(fd, 4096)
            except OSError:
                break
            if not chunk:
                break
            data += chunk
    return data
out = read_until(b'READY')
os.write(fd, b'stray paste\r')      # typed before the first question exists
out += read_until(b'First token (hidden): ')
os.write(fd, b'real-one\r')
out += read_until(b'Use it (yes)? ')
os.write(fd, b'\x04')              # Ctrl-D at the start of a line: no answer
out += read_until(b'Second token (hidden): ')
os.write(fd, b'real-two\r')
out += read_until(b'GOT-SECOND')
out += read_until(b'\n')
sys.stdout.write(out.decode('utf-8', 'replace'))
`

func TestQuestionsInARealTerminal(t *testing.T) {
	t.Setenv("QUESTIONS_HELPER", "1")
	binary, err := os.Executable()
	if err != nil {
		t.Fatal(err)
	}
	result, err := exec.Command("python3", "-c", driver, binary).CombinedOutput()
	if err != nil {
		t.Fatalf("driver: %v\n%s", err, result)
	}
	screen := strings.ReplaceAll(string(result), "\r\n", "\n")
	for _, want := range []string{
		ignoredTypedAhead,             // the stray paste was dropped, and the screen says so
		"GOT-FIRST=real-one ERR=none", // and did not answer the first question
		"GOT-SECOND=real-two ERR=none",
	} {
		if !strings.Contains(screen, want) {
			t.Errorf("the screen lacks %q:\n%s", want, screen)
		}
	}
	if strings.Contains(screen, "GOT-FIRST=stray") {
		t.Errorf("the typed-ahead paste answered the question:\n%s", screen)
	}
	// Never two questions on one line.
	for _, line := range strings.Split(screen, "\n") {
		if strings.Count(line, "(hidden):")+strings.Count(line, "(yes)?") > 1 {
			t.Errorf("two questions on one line: %q\n%s", line, screen)
		}
	}
}

func errText(err error) string {
	if err == nil {
		return "none"
	}
	return err.Error()
}

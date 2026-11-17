package main

import (
	"bufio"
	"errors"
	"fmt"
	"os"
	"strings"
	"sync"
	"syscall"
	"unsafe"
)

// The hidden prompt turns the terminal's echo off with the standard
// library's ioctl, so the command needs no dependency for it. The terminal
// constants differ by system: terminal_linux.go and terminal_darwin.go.

var (
	terminalMutex sync.Mutex
	savedTerminal *syscall.Termios
	stdinReader   = bufio.NewReader(os.Stdin)
)

var errNoTerminal = errors.New("this command asks for keys at hidden prompts, so it needs your own terminal. Run it in your desk terminal, not through a pipe or your coding agent")

// errEmptyValue is Enter at a hidden prompt with nothing typed, which
// go-live answers by asking again.
var errEmptyValue = errors.New("the value was empty")

func getTermios(fd uintptr) (*syscall.Termios, error) {
	var state syscall.Termios
	if _, _, errno := syscall.Syscall(syscall.SYS_IOCTL, fd, ioctlGetTermios, uintptr(unsafe.Pointer(&state))); errno != 0 {
		return nil, errno
	}
	return &state, nil
}

func setTermios(fd uintptr, state *syscall.Termios) error {
	if _, _, errno := syscall.Syscall(syscall.SYS_IOCTL, fd, ioctlSetTermios, uintptr(unsafe.Pointer(state))); errno != 0 {
		return errno
	}
	return nil
}

func stdinIsTerminal() bool {
	_, err := getTermios(os.Stdin.Fd())
	return err == nil
}

// readHiddenLine prints label and reads one line with echo off.
func readHiddenLine(label string) (string, error) {
	fd := os.Stdin.Fd()
	state, err := getTermios(fd)
	if err != nil {
		return "", errNoTerminal
	}
	hidden := *state
	hidden.Lflag &^= syscall.ECHO
	hidden.Lflag |= syscall.ICANON | syscall.ISIG
	terminalMutex.Lock()
	savedTerminal = state
	terminalMutex.Unlock()
	// Echo goes off before the label shows, so a value pasted as soon as the
	// label appears never shows on the screen.
	if err := setTermios(fd, &hidden); err != nil {
		return "", err
	}
	fmt.Fprint(os.Stdout, label)
	line, readErr := stdinReader.ReadString('\n')
	restoreTerminal()
	fmt.Fprintln(os.Stdout)
	if readErr != nil {
		return "", errors.New("no value was entered")
	}
	value := strings.TrimRight(line, "\r\n")
	value = strings.TrimSpace(value)
	if value == "" {
		return "", errEmptyValue
	}
	return value, nil
}

// readVisibleLine prints label and reads one line, shown as typed.
func readVisibleLine(label string) (string, error) {
	if !stdinIsTerminal() {
		return "", errNoTerminal
	}
	fmt.Fprint(os.Stdout, label)
	line, err := stdinReader.ReadString('\n')
	if err != nil {
		return "", errors.New("no answer was entered")
	}
	return strings.TrimSpace(line), nil
}

// restoreTerminal turns echo back on after an interrupted hidden prompt.
func restoreTerminal() {
	terminalMutex.Lock()
	defer terminalMutex.Unlock()
	if savedTerminal != nil {
		_ = setTermios(os.Stdin.Fd(), savedTerminal)
		savedTerminal = nil
	}
}

// clearTerminal clears the screen and its scrollback, so a secret shown on
// the screen does not stay there.
func clearTerminal() {
	fmt.Fprint(os.Stdout, "\033[3J\033[H\033[2J")
}

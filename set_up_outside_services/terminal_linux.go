package main

import (
	"syscall"
	"unsafe"
)

const (
	ioctlGetTermios = syscall.TCGETS
	ioctlSetTermios = syscall.TCSETS
	// tcflsh is TCFLSH, which package syscall lacks.
	tcflsh = 0x540b
)

// unreadTerminalBytes counts the keys typed and not yet read.
func unreadTerminalBytes(fd uintptr) int {
	var waiting int32
	if _, _, errno := syscall.Syscall(syscall.SYS_IOCTL, fd, syscall.TIOCINQ, uintptr(unsafe.Pointer(&waiting))); errno != 0 {
		return 0
	}
	return int(waiting)
}

// flushUnreadTerminalInput throws away the keys typed and not yet read
// (tcflush with TCIFLUSH, which is 0).
func flushUnreadTerminalInput(fd uintptr) {
	_, _, _ = syscall.Syscall(syscall.SYS_IOCTL, fd, tcflsh, 0)
}

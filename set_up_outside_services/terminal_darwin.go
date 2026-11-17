package main

import (
	"syscall"
	"unsafe"
)

// The desk runs Linux. This file lets the unit tests build on a Mac.
const (
	ioctlGetTermios = syscall.TIOCGETA
	ioctlSetTermios = syscall.TIOCSETA
	// fionread is FIONREAD, which package syscall lacks on macOS.
	fionread = 0x4004667f
)

// unreadTerminalBytes counts the keys typed and not yet read.
func unreadTerminalBytes(fd uintptr) int {
	var waiting int32
	if _, _, errno := syscall.Syscall(syscall.SYS_IOCTL, fd, fionread, uintptr(unsafe.Pointer(&waiting))); errno != 0 {
		return 0
	}
	return int(waiting)
}

// flushUnreadTerminalInput throws away the keys typed and not yet read
// (TIOCFLUSH with FREAD, which is 1).
func flushUnreadTerminalInput(fd uintptr) {
	flush := int32(1)
	_, _, _ = syscall.Syscall(syscall.SYS_IOCTL, fd, syscall.TIOCFLUSH, uintptr(unsafe.Pointer(&flush)))
}

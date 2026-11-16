package main

import "syscall"

// The desk runs Linux. This file lets the unit tests build on a Mac.
const (
	ioctlGetTermios = syscall.TIOCGETA
	ioctlSetTermios = syscall.TIOCSETA
)

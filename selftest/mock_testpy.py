#!/usr/bin/env python3
"""
Mock of U-Boot's test/py/test.py for the tbot selftest.

It uses the hook scripts the way test/py does (see test/py/console_board.py
in U-Boot): u-boot-test-console for the console, u-boot-test-reset before
the first command and u-boot-test-release at the end.  With --lab-mode it
expects the lab mode messages of test/py/console_base.py before the board
is ready.  It sends one command and checks its output.  The directory
given with --build-dir must hold a .config.
"""

import os
import re
import select
import signal
import subprocess
import sys
import time

PATTERN_LAB_MODE = re.compile(b"{lab mode.*}")
PATTERN_READY = re.compile(b"{lab ready in (.*)s: (.*)}")


class Console:
    """Output of the console hook, read with a timeout."""

    def __init__(self, con: "subprocess.Popen[bytes]") -> None:
        assert con.stdout is not None
        self.fd = con.stdout.fileno()
        self.buf = b""

    def read_until(self, pattern: bytes, timeout: float) -> None:
        end = time.monotonic() + timeout
        while True:
            m = re.search(pattern, self.buf)
            if m is not None:
                # keep what follows the match for the next call
                self.buf = self.buf[m.end() :]
                return
            remaining = end - time.monotonic()
            if remaining <= 0:
                sys.exit(f"mock test.py: {pattern!r} not found in {self.buf!r}")
            if select.select([self.fd], [], [], remaining)[0]:
                self.buf += os.read(self.fd, 4096)


def main() -> None:
    lab_mode = "--lab-mode" in sys.argv
    board = sys.argv[sys.argv.index("--board-type") + 1]
    builddir = sys.argv[sys.argv.index("--build-dir") + 1]
    if not os.path.exists(os.path.join(builddir, ".config")):
        sys.exit(f"mock test.py: no .config in --build-dir {builddir}")

    con = subprocess.Popen(
        ["u-boot-test-console", board, "na"],
        stdin=subprocess.PIPE,
        stdout=subprocess.PIPE,
        stderr=subprocess.DEVNULL,
        # its own process group, to stop the hook with all its children
        start_new_session=True,
    )
    assert con.stdin is not None
    console = Console(con)
    try:
        subprocess.run(["u-boot-test-reset", board, "na"], check=True)

        if lab_mode:
            console.read_until(PATTERN_LAB_MODE.pattern, 10)
            console.read_until(PATTERN_READY.pattern, 10)

        con.stdin.write(b"echo tbot-mock-$((40 + 2))\r")
        con.stdin.flush()
        console.read_until(b"tbot-mock-42", 30)
        print("mock test.py: command output received")
    finally:
        os.killpg(con.pid, signal.SIGKILL)
        con.wait()
    subprocess.run(["u-boot-test-release", board, "na"], check=True)
    print("mock test.py: passed")


if __name__ == "__main__":
    main()

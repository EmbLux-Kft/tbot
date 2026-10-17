import os
from typing import Any

import testmachines

import tbot
from tbot.machine import linux
from tbot_contrib import uboot

MOCK_TESTPY = os.path.join(os.path.dirname(__file__), "..", "..", "mock_testpy.py")


def _mock_uboot_sources(h: linux.LinuxShell) -> linux.Path:
    """A U-Boot tree that only has what testpy() checks, and a mock test/py."""
    src = h.workdir / "u-boot"
    h.exec0("rm", "-rf", src)
    h.exec0("mkdir", "-p", src / "test" / "py", src / "include")
    (src / ".config").write_text("")
    (src / "include" / "autoconf.mk").write_text("")
    testpy = src / "test" / "py" / "test.py"
    h.exec0("cp", linux.Path(h, os.path.abspath(MOCK_TESTPY)), testpy)
    h.exec0("chmod", "+x", testpy)
    return src


def _teardown_boards(ctx: tbot.Context) -> None:
    # other tests keep the board machines alive, testpy() resets them
    ctx.teardown_if_alive(testmachines.MockhwBoardLinux)
    ctx.teardown_if_alive(testmachines.MockhwBoardUBoot)
    ctx.teardown_if_alive(testmachines.MockhwBoard)


class MockTestpyHost(testmachines.Localhost):
    """
    Local host for test/py.  testpy() puts its hooks into the workdir of this
    host, and clones of the selftest lab host, which the board machines make,
    wipe the workdir of the lab host.
    """

    name = "local-testpy"

    @property
    def workdir(self) -> linux.Path:
        return linux.Workdir.xdg_runtime(self, "selftest-data-testpy")

    def init(self) -> None:
        self.exec0("mkdir", "-p", self.workdir)


def test_testpy(tbot_context: tbot.Context, monkeypatch: Any) -> None:
    # testpy() requests the board machines from tbot.ctx
    monkeypatch.setattr(tbot, "ctx", tbot_context)
    _teardown_boards(tbot_context)
    with MockTestpyHost() as bh:
        # hooks of an earlier run must not hide a missing one
        bh.exec0("rm", "-rf", bh.workdir / "uboot-testpy-tbot")
        uboot.testpy(_mock_uboot_sources(bh))


def test_testpy_builddir(tbot_context: tbot.Context, monkeypatch: Any) -> None:
    monkeypatch.setattr(tbot, "ctx", tbot_context)
    _teardown_boards(tbot_context)
    with MockTestpyHost() as bh:
        bh.exec0("rm", "-rf", bh.workdir / "uboot-testpy-tbot")
        src = _mock_uboot_sources(bh)
        builddir = bh.workdir / "u-boot-build"
        bh.exec0("rm", "-rf", builddir)
        bh.exec0("mkdir", "-p", builddir / "include")
        bh.exec0("mv", src / ".config", builddir / ".config")
        bh.exec0("mv", src / "include" / "autoconf.mk", builddir / "include")
        uboot.testpy(src, uboot_builddir=builddir)


def test_testpy_lab_mode(tbot_context: tbot.Context, monkeypatch: Any) -> None:
    monkeypatch.setattr(tbot, "ctx", tbot_context)
    _teardown_boards(tbot_context)
    with MockTestpyHost() as bh:
        bh.exec0("rm", "-rf", bh.workdir / "uboot-testpy-tbot")
        uboot.testpy(_mock_uboot_sources(bh), lab_mode=True, testpy_args=["--lab-mode"])

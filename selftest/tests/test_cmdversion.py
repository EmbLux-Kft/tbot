import pytest

import tbot
from tbot.machine import linux
from tbot.machine.linux import cmdversion
from tbot.machine.linux.cmdversion import CmdVersion

import testmachines


class TestCmdVersion:
    def test_str_and_parse(self) -> None:
        for text in ("busybox:1.37.0", "procps-ng:4.0.6", "full:unknown", "notfound"):
            assert str(CmdVersion.parse(text)) == text

    def test_unknown_version(self) -> None:
        v = CmdVersion.parse("full:unknown")
        assert v.version is None
        assert v.found and not v.is_busybox

    def test_notfound(self) -> None:
        v = CmdVersion.parse("notfound")
        assert not v.found and not v.is_busybox

    def test_busybox(self) -> None:
        assert CmdVersion.parse("busybox:1.37.0").is_busybox

    def test_version_tuple(self) -> None:
        assert CmdVersion("busybox", "1.37.0").version_tuple() == (1, 37, 0)
        assert CmdVersion("net-tools", "2.10-alpha").version_tuple() == (2, 10)
        assert CmdVersion("full").version_tuple() == ()

    def test_eq_with_str(self) -> None:
        assert CmdVersion("busybox", "1.37.0") == "busybox:1.37.0"

    def test_parse_bad(self) -> None:
        with pytest.raises(ValueError):
            CmdVersion.parse("busybox")


# first lines of real version outputs (Fedora, a Yocto lab host, a Yocto
# board)
OUTPUTS = [
    ("  procps-ng 3.3.16", "procps-ng:3.3.16"),
    ("ps from procps-ng 3.3.16", "procps-ng:3.3.16"),
    ("hexdump from util-linux 2.41.5", "util-linux:2.41.5"),
    ("ip utility, iproute2-6.19.0", "iproute2:6.19.0"),
    ("iperf 3.21 (cJSON 1.7.15)", "iperf3:3.21"),
    ("net-tools 2.10-alpha", "net-tools:2.10-alpha"),
    ("dd (coreutils) 9.10", "coreutils:9.10"),
    ("grep (GNU grep) 3.4", "grep:3.4"),
    ("flash_erase (mtd-utils) 2.3.1", "mtd-utils:2.3.1"),
    ("GNU Awk 5.1.0, API: 3.0 (GNU MPFR 4.1.0-p13, GNU MP 6.2.0)", "gawk:5.1.0"),
    ("ethtool version 6.19", "ethtool:6.19"),
    ("ps from procps-ng 4.0.6-dirty", "procps-ng:4.0.6-dirty"),
    ("i2cdetect version 4.4", "i2c-tools:4.4"),
]


@pytest.mark.parametrize("output,expected", OUTPUTS)  # type: ignore
def test_parse_version_output(output: str, expected: str) -> None:
    assert str(cmdversion.parse_version_output(output)) == expected


def test_parse_version_output_none() -> None:
    assert cmdversion.parse_version_output("top: invalid option -- 'v'") is None


def test_parse_busybox_banner() -> None:
    assert (
        cmdversion.parse_busybox_banner("BusyBox v1.37.0 () multi-call binary.")
        == "1.37.0"
    )
    assert cmdversion.parse_busybox_banner("nothing") is None


def test_cmd_get_version_notfound(tbot_context: tbot.Context) -> None:
    with tbot_context.request(testmachines.Localhost) as lo:
        v = lo.cmd_get_version("tbot-no-such-command")
        assert not v.found
        assert str(v) == "notfound"


def test_cmd_get_version_found(tbot_context: tbot.Context) -> None:
    with tbot_context.request(testmachines.Localhost) as lo:
        v = lo.cmd_get_version("ls")
        assert v.found
        assert v.path is not None and "/" in v.path


def test_cmd_get_version_preset(tbot_context: tbot.Context) -> None:
    with tbot_context.request(testmachines.Localhost) as lo:
        lo.cmd_versions_set({"tbot-no-such-command": "busybox:1.2.3"})
        assert lo.cmd_get_version("tbot-no-such-command") == "busybox:1.2.3"


def test_cmd_get_version_refresh(tbot_context: tbot.Context) -> None:
    """refresh=True finds it out again, the preset is replaced"""
    with tbot_context.request(testmachines.Localhost) as lo:
        lo.cmd_versions_set({"tbot-no-such-command": "busybox:1.2.3"})
        assert lo.cmd_get_version("tbot-no-such-command", refresh=True) == "notfound"
        assert lo.cmd_get_version("tbot-no-such-command") == "notfound"


def test_cmd_get_version_busybox(tbot_context: tbot.Context) -> None:
    """a command linked to an executable named busybox is a busybox applet"""
    with tbot_context.request(testmachines.Localhost) as lo:
        d = lo.workdir / "cmdversion-test"
        lo.exec0("rm", "-rf", d)
        lo.exec0("mkdir", "-p", d)
        (d / "busybox").write_text(
            "#!/bin/sh\necho 'BusyBox v9.8.7 () multi-call binary.'\n"
        )
        lo.exec0("chmod", "+x", d / "busybox")
        lo.exec0("ln", "-s", "busybox", d / "tbot-bb-applet")
        path = lo.env("PATH")
        lo.env("PATH", f"{d._local_str()}:{path}")
        try:
            v = lo.cmd_get_version("tbot-bb-applet")
        finally:
            lo.env("PATH", path)
            lo.exec0("rm", "-rf", d)
        assert v == "busybox:9.8.7"
        assert v.is_busybox


def test_cmd_get_version_probes_in_order(tbot_context: tbot.Context) -> None:
    """top of procps-ng 3 does not know -V, the next probe -v matches"""
    with tbot_context.request(testmachines.Localhost) as lo:
        d = lo.workdir / "cmdversion-test"
        lo.exec0("rm", "-rf", d)
        lo.exec0("mkdir", "-p", d)
        (d / "top").write_text(
            "#!/bin/sh\n"
            "[ \"$1\" = -v ] && { echo '  procps-ng 3.3.16'; exit 0; }\n"
            "echo \"top: unknown option '$1'\"; exit 1\n"
        )
        lo.exec0("chmod", "+x", d / "top")
        path = lo.env("PATH")
        lo.env("PATH", f"{d._local_str()}:{path}")
        try:
            v = lo.cmd_get_version("top", refresh=True)
        finally:
            lo.env("PATH", path)
            lo.exec0("rm", "-rf", d)
        assert v == "procps-ng:3.3.16"


def test_cmd_get_version_alias(tbot_context: tbot.Context) -> None:
    """an alias of the login shell does not hide the program"""
    with tbot_context.request(testmachines.Localhost) as lo:
        d = lo.workdir / "cmdversion-test"
        lo.exec0("rm", "-rf", d)
        lo.exec0("mkdir", "-p", d)
        (d / "tbot-aliased").write_text("#!/bin/sh\necho 'tbot-aliased 1.0'\n")
        lo.exec0("chmod", "+x", d / "tbot-aliased")
        path = lo.env("PATH")
        lo.env("PATH", f"{d._local_str()}:{path}")
        lo.exec0(linux.Raw("alias tbot-aliased='tbot-aliased --color=auto'"))
        try:
            v = lo.cmd_get_version("tbot-aliased", refresh=True)
        finally:
            lo.exec0(linux.Raw("unalias tbot-aliased"))
            lo.env("PATH", path)
            lo.exec0("rm", "-rf", d)
        assert v == "full:unknown"
        assert v.path == f"{d._local_str()}/tbot-aliased"


def test_cmd_get_version_once(tbot_context: tbot.Context) -> None:
    """the second call returns the cached answer without asking the machine"""
    with tbot_context.request(testmachines.Localhost) as lo:
        first = lo.cmd_get_version("ls")
        calls = []
        orig = lo.exec

        def counting_exec(*args):  # type: ignore
            calls.append(args)
            return orig(*args)

        lo.exec = counting_exec  # type: ignore
        try:
            assert lo.cmd_get_version("ls") == first
        finally:
            del lo.exec  # type: ignore
        assert calls == []


def test_cmd_get_version_autoinstall(tbot_context: tbot.Context) -> None:
    """autoinstall asks install_package() and looks again"""
    with tbot_context.request(testmachines.Localhost) as lo:
        asked = []

        def install(cmd):  # type: ignore
            asked.append(cmd)
            return False

        lo.install_package = install  # type: ignore
        try:
            assert not lo.cmd_get_version(
                "tbot-no-such-command-2", autoinstall=True
            ).found
            assert not lo.cmd_get_version("tbot-no-such-command-3").found
        finally:
            del lo.install_package  # type: ignore
        assert asked == ["tbot-no-such-command-2"]

# tbot, Embedded Automation Tool
# Copyright (C) 2026  Heiko Schocher
#
# This program is free software: you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with this program.  If not, see <https://www.gnu.org/licenses/>.

"""
Which implementation and version of a command a linux machine has.

The output of a command depends on where it comes from: ``top`` of busybox
prints other columns than ``top`` of procps-ng, and the version of a
program can change its output as well.  :py:class:`CmdVersion` describes
one command on one machine, :py:meth:`LinuxShell.cmd_get_version()
<tbot.machine.linux.LinuxShell.cmd_get_version>` finds it out.
"""

import re
import typing

__all__ = ("CmdVersion", "PROBES", "PATTERNS", "IMPL_NAMES", "FIXED_IMPL")


class CmdVersion:
    """
    Implementation and version of a command on a linux machine.

    ``str()`` gives ``<impl>:<version>``, for example ``busybox:1.37.0``,
    ``procps-ng:4.0.6`` or ``full:unknown``, and ``notfound`` for a command
    the machine does not have.  :py:meth:`parse` reads that back, so the
    strings can be kept in a configuration.

    :param impl: ``busybox``, the project the program comes from (as its
        version output names it, e.g. ``procps-ng``, ``util-linux``,
        ``coreutils``), ``shell-builtin``, ``full`` when it is not busybox
        but the project is not known, or ``notfound``.
    :param version: the version, ``None`` if not known.
    :param path: where the command was found, ``None`` if not known.
    """

    NOTFOUND = "notfound"

    def __init__(
        self,
        impl: str,
        version: typing.Optional[str] = None,
        path: typing.Optional[str] = None,
    ) -> None:
        self.impl = impl
        self.version = version
        self.path = path

    @property
    def found(self) -> bool:
        """``False`` if the machine does not have the command."""
        return self.impl != self.NOTFOUND

    @property
    def is_busybox(self) -> bool:
        """``True`` if the command is a busybox applet."""
        return self.impl == "busybox"

    def version_tuple(self) -> typing.Tuple[int, ...]:
        """
        The leading numbers of the version, for comparisons, e.g.
        ``(1, 37, 0)`` for ``1.37.0`` and ``(2, 10)`` for ``2.10-alpha``;
        an empty tuple if the version is not known.
        """
        if not self.version:
            return ()
        m = re.match(r"\d+(\.\d+)*", self.version)
        if m is None:
            return ()
        return tuple(int(n) for n in m.group(0).split("."))

    @classmethod
    def parse(cls, text: str) -> "CmdVersion":
        """
        Read a ``str()`` of a :py:class:`CmdVersion` back, e.g. from a
        configuration file.
        """
        text = text.strip()
        if text == cls.NOTFOUND:
            return cls(cls.NOTFOUND)
        impl, sep, version = text.partition(":")
        if not impl or not sep:
            raise ValueError(f"{text!r}: not <impl>:<version> or notfound")
        return cls(impl, None if version in ("", "unknown") else version)

    def __str__(self) -> str:
        if not self.found:
            return self.NOTFOUND
        return f"{self.impl}:{self.version or 'unknown'}"

    def __repr__(self) -> str:
        return f"CmdVersion({str(self)!r}, path={self.path!r})"

    def __eq__(self, other: object) -> bool:
        if isinstance(other, str):
            return str(self) == other
        if isinstance(other, CmdVersion):
            return str(self) == str(other)
        return NotImplemented

    def __hash__(self) -> int:
        return hash(str(self))


#: The argument that makes a command print its version and exit, or a
#: tuple of them, tried in this order until the output matches.  Only the
#: commands named here are run for their version; running an unknown command
#: with ``--version`` could do something else (``devmem2 --version`` would
#: read ``--version`` as an address).  Extend it for other commands.
PROBES: typing.Dict[str, typing.Union[str, typing.Tuple[str, ...]]] = {
    # procps-ng 4 knows -V only, procps-ng 3 -v only
    "top": ("-V", "-v"),
    "ps": "--version",
    "free": "--version",
    "pgrep": "--version",
    "kill": "--version",
    "hexdump": "--version",
    "dmesg": "--version",
    "mount": "--version",
    "dd": "--version",
    "cat": "--version",
    "ls": "--version",
    "md5sum": "--version",
    "grep": "--version",
    "sed": "--version",
    "awk": "--version",
    "tar": "--version",
    "ip": "-V",
    "ifconfig": "--version",
    "iperf3": "--version",
    "ethtool": "--version",
    "flash_erase": "--version",
    "nandwrite": "--version",
    "mtdinfo": "--version",
    "i2cdetect": "-V",
}

#: Regular expressions for the version output, tried in this order; group 1
#: is the project, group 2 the version.
PATTERNS: typing.List[str] = [
    r"from ([\w.+-]+) (\d[\w.+-]*)",  # procps-ng, util-linux
    r"\((?:GNU )?([\w.+-]+)\) (\d[\w.+-]*)",  # coreutils, grep, sed, mtd-utils
    r"(iproute2)-(\d[\w.+-]*)",  # ip
    r"^(procps(?:-ng)?) (\d[\w.+-]*)",  # top -v of procps-ng 3
    r"^(iperf) (3[\w.+-]*)",  # iperf3
    r"^(net-tools) (\d[\w.+-]*)",  # ifconfig
    r"^GNU (Awk) (\d[\w.+-]*)",  # gawk
    r"^(ethtool) version (\d[\w.+-]*)",
    r"^(i2cdetect) version (\d[\w.+-]*)",
]

#: Project names as the version output spells them, mapped to the name
#: :py:class:`CmdVersion` uses.
IMPL_NAMES: typing.Dict[str, str] = {
    "iperf": "iperf3",
    "Awk": "gawk",
    "procps": "procps-ng",
    "i2cdetect": "i2c-tools",
}

#: Commands without a version output whose implementation is known from
#: the name alone.
FIXED_IMPL: typing.Dict[str, str] = {
    "devmem2": "devmem2",
}


def parse_version_output(output: str) -> typing.Optional[CmdVersion]:
    """
    The :py:class:`CmdVersion` a version output names, ``None`` if no
    pattern of :py:data:`PATTERNS` matches.
    """
    for line in output.splitlines():
        line = line.strip()
        for pattern in PATTERNS:
            m = re.search(pattern, line)
            if m is not None:
                impl = IMPL_NAMES.get(m.group(1), m.group(1))
                return CmdVersion(impl, m.group(2))
    return None


def parse_busybox_banner(output: str) -> typing.Optional[str]:
    """
    The version from the banner of busybox, e.g. ``1.37.0`` from
    ``BusyBox v1.37.0 () multi-call binary.``; ``None`` if there is none.
    """
    m = re.search(r"BusyBox v(\d[\w.+-]*)", output)
    return m.group(1) if m else None

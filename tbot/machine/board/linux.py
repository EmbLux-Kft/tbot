# tbot, Embedded Automation Tool
# Copyright (C) 2019  Harald Seiler
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

import abc
import contextlib
import typing

import tbot
import tbot.error
from .. import machine, board, channel, connector


class LinuxStartupEvent(tbot.log.EventIO):
    def __init__(self, lnx: machine.Machine) -> None:
        self.lnx = lnx
        super().__init__(
            ["board", "linux", lnx.name],
            tbot.log.c("LINUX").bold + f" ({lnx.name})",
            verbosity=tbot.log.Verbosity.QUIET,
        )

        self.prefix = "   <> "
        self.verbosity = tbot.log.Verbosity.STDOUT

    def close(self) -> None:
        setattr(self.lnx, "bootlog", self.getvalue())
        self.data["output"] = self.getvalue()
        super().close()


class LinuxBoot(machine.Machine):
    _linux_init_event: typing.Optional[tbot.log.EventIO] = None

    def _linux_boot_event(self) -> tbot.log.EventIO:
        if self._linux_init_event is None:
            self._linux_init_event = LinuxStartupEvent(self)

        return self._linux_init_event


class LinuxBootLogin(machine.Initializer, LinuxBoot):
    """
    Machine :py:class:`~tbot.machine.Initializer` to wait for linux boot-up and
    automatically login.

    Use this initializer whenever you have a serial-console for a Linux system.

    **Example**:

    .. code-block:: python

        from tbot.machine import board, linux

        class StandaloneLinux(
            board.Connector,
            board.LinuxBootLogin,
            linux.Bash,
        ):
            # board.LinuxBootLogin config:
            username = "root"
            password = "hunter2"
    """

    login_prompt = "login: "
    """Prompt that indicates tbot should send the username."""

    login_delay = 0
    """
    The delay between first occurence of login_prompt and actual login.

    This delay might be necessary if your system clutters the login prompt with
    log-messages during the first few seconds after boot.
    """

    bootlog: str
    """Log of kernel-messages which were output during boot."""

    @property
    @abc.abstractmethod
    def username(self) -> str:
        """Username to login as."""
        pass

    @property
    @abc.abstractmethod
    def password(self) -> typing.Optional[str]:
        """Password to login with.  Set to ``None`` if no password is needed."""
        pass

    @contextlib.contextmanager
    def _init_machine(self) -> typing.Iterator:
        with contextlib.ExitStack() as cx:
            ev = cx.enter_context(self._linux_boot_event())
            cx.enter_context(self.ch.with_stream(ev))

            # On purpose do not login immediately as we may get some
            # console flooding from upper SW layers (and tbot's console
            # setup may get broken)
            if self.login_delay != 0:
                while 1:
                    try:
                        self.ch.read_until_prompt(prompt=self.login_prompt, timeout=self.login_delay)
                        break
                    except TimeoutError:
                        self.ch.sendline("")
                        pass
            else:
                self.ch.read_until_prompt(prompt=self.login_prompt)

            self.ch.sendline(self.username)
            if self.password is not None:
                self.ch.read_until_prompt(prompt="assword: ")
                self.ch.sendline(self.password)

        yield None


Self = typing.TypeVar("Self", bound="LinuxUbootConnector")


class LinuxUbootConnector(connector.Connector, LinuxBootLogin):
    """
    Connector for booting Linux from U-Boot.

    This connector can either boot from a :py:class:`~tbot.machine.board.Board`
    instance or from a :py:class:`~tbot.machine.board.UBootShell` instance.  If
    booting directly from the board, it will first initialize a U-Boot machine
    and then use it to kick off the boot to Linux.  See above for an example.
    """

    @property
    @abc.abstractmethod
    def uboot(self) -> typing.Type[board.UBootShell]:
        """
        U-Boot machine to use when booting directly from a
        :py:class:`~tbot.machine.board.Board` instance.
        """
        raise tbot.error.AbstractMethodError()

    def do_boot(self, ub: board.UBootShell) -> channel.Channel:
        """
        Boot procedure.

        An implementation of this method should use the U-Boot machine given as
        ``ub`` to kick off the Linux boot.  It should return the channel to the
        now booting Linux.  This will in almost all cases be archieved by using
        the :py:meth:`tbot.machine.board.UBootShell.boot` method.

        **Example**:

        .. code-block:: python

            from tbot.machine import board, linux

            class LinuxFromUBoot(
                board.LinuxUbootConnector,
                board.LinuxBootLogin,
                linux.Bash,
            ):
                uboot = MyUBoot  # <- Our UBoot machine

                def do_boot(self, ub):  # <- Procedure to boot Linux
                   # Any logic necessary to prepare for boot
                   ub.env("autoload", "false")
                   ub.exec0("dhcp")

                   # Return the channel using ub.boot()
                   return ub.boot("run", "nfsboot")

                ...
        """
        return ub.boot("boot")

    def __init__(self, b: typing.Union[board.Board, board.UBootShell]) -> None:
        self._b = b

    @contextlib.contextmanager
    def _connect(self) -> typing.Iterator[channel.Channel]:
        with contextlib.ExitStack() as cx:
            if isinstance(self._b, board.Board):
                ub = cx.enter_context(self.uboot(self._b))  # type: ignore
            elif isinstance(self._b, board.UBootShell):
                ub = cx.enter_context(self._b)
            else:
                raise TypeError(f"Got {self._b!r} instead of Board/U-Boot machine")

            self._linux_boot_event()

            yield self.do_boot(ub).take()

    def clone(self: Self) -> Self:
        """This machine cannot be cloned."""
        raise NotImplementedError("can't clone Linux_U-Boot Machine")

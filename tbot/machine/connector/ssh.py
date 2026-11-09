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
from . import connector
from .. import linux, channel
from ..linux import auth

Self = typing.TypeVar("Self", bound="SSHConnector")

# What ssh prints when a host key does not match its known_hosts, for
# the machine itself or for a jump host on the way to it.
_HOSTKEY_MESSAGES = (
    "REMOTE HOST IDENTIFICATION HAS CHANGED",
    "Host key verification failed",
    "host key check failure",
)


class SSHConnector(connector.Connector):
    """
    Connect to remote using ``ssh`` by starting off from an existing machine.

    An :py:class:`SSHConnector` is different from a
    :py:class:`ParamikoConnector` as it requires an existing machine to start
    the connection from.  This allows jumping via one host to a second.

    **Example**:

    .. code-block:: python

        import tbot
        from tbot.machine import connector, linux

        # Connect into a container running on the (possibly remote) lab-host
        class MyRemote(
            connector.SSHConnector,
            linux.Bash,
        ):
            hostname = "localhost"
            port = 20220
            username = "root"

        with tbot.acquire_lab() as lh:
            # lh might be a ParamikoConnector machine.
            with MyRemote(lh) as ssh_session:
                ssh_session.exec0("uptime")
    """

    @property
    def ignore_hostkey(self) -> bool:
        """
        Ignore host key.

        Set this to true if the remote changes its host key often.
        """
        return False

    @property
    def check_hostkey(self) -> bool:
        """
        Stop with :py:class:`tbot.error.HostKeyError` when ssh reports a host
        key which does not match its ``known_hosts``.

        ssh does not refuse such a connection when ``StrictHostKeyChecking``
        is ``no``: it logs in, but turns off password authentication and
        forwarding.  A ``ProxyJump`` then breaks off with ``forwarding
        disabled due to host key check failure`` and the shell of the new
        machine never shows up, and the reason ends up in the log only
        among the output of the channel.

        To catch this, tbot runs the ssh command once with ``true`` before
        it logs in and reads what ssh prints.  This costs one more ssh
        connection per machine.  Return ``False`` to skip it.  It is
        skipped as well when :py:attr:`ignore_hostkey` is set.

        .. versionadded:: UNRELEASED
        """
        return True

    @property
    def requires_legacy_scp(self) -> bool:
        """
        Use the legacy SCP protocol for file transfers instead of the SFTP protocol.

        Forcing the use of the SCP protocol may be necessary for servers that do not
        implement SFTP, for backwards compatibility.

        .. versionadded:: 0.10.10
        """
        return False

    @property
    def use_multiplexing(self) -> bool:
        """
        Whether tbot should attempt to enable connection multiplexing.

        Connection multiplexing is a mechanism to share a connection between
        multiple sessions.  This can drastically speed up your tests when many
        connections to the same machine are opened and closed.  Refer to
        `ControlMaster in sshd_config(5)`_ for details.

        .. _ControlMaster in sshd_config(5): https://man.openbsd.org/ssh_config.5#ControlMaster

        .. versionadded:: 0.9.0
        """
        return False

    @property
    @abc.abstractmethod
    def hostname(self) -> str:
        """
        Return the hostname of this machine.

        :rtype: str
        """
        pass

    @property
    def username(self) -> str:
        """
        Return the username for logging in on this machine.

        Defaults to the username on the labhost.
        """
        return self.host.username

    @property
    def authenticator(self) -> auth.Authenticator:
        """
        Return an authenticator that allows logging in on this machine.

        See :mod:`tbot.machine.linux.auth` for available authenticators.

        .. danger::
            It is strongly advised to use key authentication.  If you use password
            auth, **THE PASSWORD WILL BE LEAKED** and **MIGHT EASILY BE STOLEN**
            by other users on your labhost.  It will also be visible in the log file.

            If you decide to use this, you're doing this on your own risk.

            The only case where I support using passwords is when connecting to
            a test board with a default password.

        :rtype: tbot.machine.linux.auth.Authenticator
        """
        return auth.NoneAuthenticator()

    @property
    def port(self) -> int:
        """
        Return the port the SSH server is listening on.

        :rtype: int
        """
        return 22

    @property
    def ssh_config(self) -> typing.List[str]:
        """
        Add additional ssh config options when connecting.

        **Example**::

            class MySSHMach(connector.SSHConnector, linux.Bash):
                ssh_config = ["ProxyJump=foo@example.com"]

        :rtype: list(str)

        .. versionadded:: 0.6.2
        """
        return []

    def __init__(self, host: typing.Optional[linux.LinuxShell] = None) -> None:
        self.host: linux.LinuxShell
        self.host = host  # type: ignore

    @classmethod
    @contextlib.contextmanager
    def from_context(
        cls: typing.Type[Self], ctx: "tbot.Context"
    ) -> typing.Iterator[Self]:
        with contextlib.ExitStack() as cx:
            lh = None
            if not issubclass(cls, ctx.get_machine_class(tbot.role.LabHost)):
                lh = cx.enter_context(ctx.request(tbot.role.LabHost))
            m = cx.enter_context(cls(lh))  # type: ignore
            yield typing.cast(Self, m)

    @contextlib.contextmanager
    def _connect(self) -> typing.Iterator[channel.Channel]:
        with contextlib.ExitStack() as cx:
            if self.host is None:
                self.host = cx.enter_context(tbot.acquire_local())
            h = cx.enter_context(self.host.clone())

            authenticator = self.authenticator
            if isinstance(authenticator, auth.NoneAuthenticator):
                cmd = ["ssh", "-o", "BatchMode=yes"]
            elif isinstance(authenticator, auth.PrivateKeyAuthenticator):
                cmd = [
                    "ssh",
                    "-o",
                    "BatchMode=yes",
                    "-i",
                    authenticator.get_key_for_host(h),
                ]
            elif isinstance(authenticator, auth.PasswordAuthenticator):
                cmd = ["sshpass", "-p", authenticator.password, "ssh"]
            else:
                if typing.TYPE_CHECKING:
                    authenticator._undefined_marker
                raise ValueError(f"Unknown authenticator {authenticator!r}")

            hk_disable = (
                ["-o", "StrictHostKeyChecking=no"] if self.ignore_hostkey else []
            )

            multiplexing = []
            if self.use_multiplexing:
                multiplexing_dir = self.host.workdir / ".ssh-multi"
                self.host.exec0("mkdir", "-p", multiplexing_dir)

                multiplexing += ["-o", "ControlMaster=auto"]
                multiplexing += ["-o", "ControlPersist=10m"]
                multiplexing += [
                    "-o",
                    f"ControlPath={multiplexing_dir.at_host(self.host)}/%C",
                ]

            args = [
                *cmd,
                *hk_disable,
                *multiplexing,
                *["-p", str(self.port)],
                *[arg for opt in self.ssh_config for arg in ["-o", opt]],
                f"{self.username}@{self.hostname}",
            ]

            if self.check_hostkey and not self.ignore_hostkey:
                self._check_hostkey(h, args)

            with h.open_channel(*args) as ch:
                yield ch

    def _check_hostkey(
        self, h: linux.LinuxShell, args: typing.List[typing.Any]
    ) -> None:
        _, output = h.exec(*args, "true")
        if any(msg in output for msg in _HOSTKEY_MESSAGES):
            raise tbot.error.HostKeyError(self, output.strip())

    def clone(self) -> "SSHConnector":
        """Clone this machine."""
        new = type(self)(self.host)
        new._orig = self._orig or self
        return new

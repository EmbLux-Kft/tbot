from typing import Type

import pytest
import tbot
import tbot.error
from tbot.machine import connector, linux

import testmachines


class HostKeyClientBase(connector.SSHConnector, linux.Bash):
    name = "hostkey-client"
    hostname = "localhost"
    port = 18222


def ssh_client(
    srv: testmachines.MocksshServer,
    known_hosts: str,
    check: bool = True,
    ignore: bool = False,
) -> Type[HostKeyClientBase]:
    class HostKeyClient(HostKeyClientBase):
        ignore_hostkey = ignore
        check_hostkey = check
        # ssh does not refuse a changed host key with
        # StrictHostKeyChecking=no, it only prints a warning
        ssh_config = [
            f"UserKnownHostsFile={known_hosts}",
            "StrictHostKeyChecking=no",
            "SendEnv=XDG_RUNTIME_DIR",
        ]
        authenticator = linux.auth.PrivateKeyAuthenticator(srv.userkey.at_host(srv))

    return HostKeyClient


def known_hosts(srv: testmachines.MocksshServer, right: bool) -> str:
    """known_hosts with the host key of the mock server, or another one"""
    if right:
        pubkey = srv.workdir / "ssh_host_rsa_key.pub"
    else:
        key = srv.workdir / "other_host_rsa_key"
        if not key.exists():
            srv.exec0("ssh-keygen", "-f", key, "-N", "", "-t", "rsa")
        pubkey = srv.workdir / "other_host_rsa_key.pub"

    path = srv.workdir / f"known_hosts_{'right' if right else 'wrong'}"
    path.write_text("[localhost]:18222 " + pubkey.read_text())
    return path.at_host(srv)


def test_ssh_hostkey_matches(tbot_context: tbot.Context) -> None:
    with tbot_context() as cx:
        srv = cx.request(testmachines.MocksshServer)
        lo = cx.request(tbot.role.LocalHost)
        with ssh_client(srv, known_hosts(srv, right=True))(lo) as ssh:
            assert ssh.exec0("echo", "hello") == "hello\n"


def test_ssh_hostkey_changed(tbot_context: tbot.Context) -> None:
    with tbot_context() as cx:
        srv = cx.request(testmachines.MocksshServer)
        lo = cx.request(tbot.role.LocalHost)
        kh = known_hosts(srv, right=False)
        with pytest.raises(tbot.error.HostKeyError) as e:
            with ssh_client(srv, kh)(lo):
                pass

        assert "REMOTE HOST IDENTIFICATION HAS CHANGED" in e.value.ssh_output
        # the offending line and the command to remove it
        assert kh in e.value.ssh_output
        assert "hostkey-client" in str(e.value)


@pytest.mark.parametrize("check,ignore", [(False, False), (True, True)])  # type: ignore
def test_ssh_hostkey_changed_not_checked(
    tbot_context: tbot.Context, check: bool, ignore: bool
) -> None:
    with tbot_context() as cx:
        srv = cx.request(testmachines.MocksshServer)
        lo = cx.request(tbot.role.LocalHost)
        kh = known_hosts(srv, right=False)
        with ssh_client(srv, kh, check=check, ignore=ignore)(lo) as ssh:
            assert ssh.exec0("echo", "hello") == "hello\n"

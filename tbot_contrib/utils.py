# tbot, Embedded Automation Tool
# Copyright (C) 2020  Heiko Schocher
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
import re
import typing

from tbot.machine import linux
from tbot.tc import shell


_SERVICES_CACHE: typing.Dict[str, typing.Dict[str, bool]] = {}


def ensure_sd_unit(lnx: linux.LinuxShell, services: typing.List[str]) -> None:
    """
    check if all systemd services in list services run on linux machine lnx.
    If not, try to start them.

    :param lnx: linux shell
    :param services: list of systemd services
    """
    if lnx.name not in _SERVICES_CACHE:
        _SERVICES_CACHE[lnx.name] = {}

    for s in services:
        if s in _SERVICES_CACHE[lnx.name]:
            continue

        if not lnx.test("systemctl", "is-active", s):
            lnx.exec0("sudo", "systemctl", "start", s)

        _SERVICES_CACHE[lnx.name][s] = True


_IP_CACHE: typing.Dict[typing.Tuple[linux.LinuxShell, str], str] = {}


def find_ip_address(
    lnx: linux.LinuxShell,
    route_target: typing.Optional[str] = None,
    force: bool = False,
) -> str:
    """
    Find out an IP-address of a host.

    In times where most hosts have many IP addresses, this is not as trivial as
    one would like.  This testcase approaches the problem by trying to find the
    IP-address, the host would use on a certain route.

    By default, this is the route to reach a theoretical host at ``1.0.0.0``.
    This will yield a sensible result in *most* cases but of course will not
    always be the address you want.  For more fine-grained control you can pass
    a ``route_target``.  This is the IP-address of this theoretical host to reach.

    :param linux.LinuxShell lnx: The host to work on.
    :param str route_target: An optional route target.  Defaults to ``1.0.0.0``.
    :param bool force: By default, this testcase caches results for faster
        lookup when called multiple times.  This parameter enforces a re-check
        which might be useful when the network configuration on ``lnx``
        changed.
    :rtype: str
    :returns: The IP-address which was found.
    """
    if route_target is None:
        # 1 equals to 1.0.0.0 which will probably yield a sensible route in
        # most cases.
        route_target = "1"

    if (lnx, route_target) not in _IP_CACHE:
        if shell.check_for_tool(lnx, "ip"):
            output = lnx.exec0("ip", "route", "get", route_target, linux.Pipe, "cat")
            match = re.match(
                r"\S+ (?:via \S+ )?dev \S+ src (\S+).*", output, re.DOTALL,
            )
            assert match is not None, f"Failed to parse `ip route` output ({output!r})!"
            ip = match.group(1)
        else:
            raise NotImplementedError("Found no way to find out ip-address")

        _IP_CACHE[(lnx, route_target)] = ip

    return _IP_CACHE[(lnx, route_target)]


def string_to_dict(string: str, pattern: str) -> dict:
    """
    convert a string into a dictionary via a pattern

    example pattern:
    'hello, my name is {name} and I am a {age} year old {what}'

    string:
    'hello, my name is dan and I am a 33 year old developer'

    returned dict:
    {'age': '33', 'name': 'dan', 'what': 'developer'}
    from:
    https://stackoverflow.com/questions/11844986/convert-or-unformat-a-string-to-variables-like-format-but-in-reverse-in-p
    """
    regex = re.sub(r"{(.+?)}", r"(?P<_\1>.+)", pattern)
    match = re.search(regex, string)
    assert match is not None, f"The pattern {regex!r} was not found!"
    values = list(match.groups())
    keys = re.findall(r"{(.+?)}", pattern)
    _dict = dict(zip(keys, values))
    return _dict

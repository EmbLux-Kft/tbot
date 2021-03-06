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

import typing
import tbot
from tbot.machine import linux
from tbot.tc import kconfig, selftest

__all__ = ("selftest_tc_kconfig",)


@tbot.testcase
def selftest_tc_kconfig(lab: typing.Optional[linux.Lab] = None) -> None:
    """Test kconig setting."""
    with lab or selftest.SelftestHost() as lh:
        conf = lh.workdir / "selftest-kconfig"

        for i in range(4):
            lh.exec0(
                "echo",
                """\
# tbot-selftest kconfig file
# DO NOT EDIT! (Deleting is ok, though)

CONFIG_FOO=y
CONFIG_BAR=m
# CONFIG_BAZ is not set
CONFIG_STRING="a happy string"
CONFIG_HEX=0xC0FFEE""",
                linux.RedirStdout(conf),
            )

            if i == 0:
                tbot.log.message("Enabling all ...")
                kconfig.enable(conf, "CONFIG_FOO")
                kconfig.enable(conf, "CONFIG_BAR")
                kconfig.enable(conf, "CONFIG_BAZ")

                assert (
                    lh.exec0("grep", "-c", "-E", "CONFIG_(FOO|BAR|BAZ)=y", conf).strip()
                    == "3"
                )
            elif i == 1:
                tbot.log.message("Disabling all ...")
                kconfig.disable(conf, "CONFIG_FOO")
                kconfig.disable(conf, "CONFIG_BAR")
                kconfig.disable(conf, "CONFIG_BAZ")

                assert (
                    lh.exec0("grep", "-c", "-E", "# CONFIG_(FOO|BAR|BAZ)", conf).strip()
                    == "3"
                )
                assert (
                    lh.exec("grep", "-c", "-E", "^CONFIG_(FOO|BAR|BAZ)", conf)[
                        1
                    ].strip()
                    == "0"
                )
            elif i == 2:
                tbot.log.message("Moduling all ...")
                kconfig.module(conf, "CONFIG_FOO")
                kconfig.module(conf, "CONFIG_BAR")
                kconfig.module(conf, "CONFIG_BAZ")

                assert (
                    lh.exec0("grep", "-c", "-E", "CONFIG_(FOO|BAR|BAZ)=m", conf).strip()
                    == "3"
                )
            elif i == 3:
                tbot.log.message("Testing values ...")
                kconfig.set_string_value(conf, "CONFIG_STRING", "abcdef")
                kconfig.set_hex_value(conf, "CONFIG_HEX", 0xDEADBEEF)

                assert (
                    lh.exec0("grep", "-c", 'CONFIG_STRING="abcdef"', conf).strip()
                    == "1"
                )
                assert (
                    lh.exec0("grep", "-c", "CONFIG_HEX=0xdeadbeef", conf).strip() == "1"
                )

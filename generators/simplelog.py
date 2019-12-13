#!/usr/bin/env python3
# tbot, Embedded Automation Tool
# Copyright (C) 2018  Harald Seiler
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

"""create a simple log."""
import logparser
import sys

import regex as re
def remove_control_characters(str):
    ansi_escape = re.compile(r'(?:\x1B[@-_]|[\x80-\x9F])[0-?]*[ -/]*[@-~]')
    return ansi_escape.sub('', str)

def main() -> None:
    """Main."""
    events = logparser.from_argv()

    oldtime = None
    # get u-boot machine name
    ub = sys.argv[2]
    for ev in events:
        newtime = ev.time
        if oldtime != None:
            difftime = float(newtime) - float(oldtime)
        if ev.type[0] == "cmd":
            prompt = "# "
            if ev.type[1] == ub:
                prompt = "=> "
            print (f'difftime {difftime:8} CMD @ {ev.type[1]}: ')
            print (f'{prompt}{ev.data["cmd"]}')
            try:
                buf = ev.data["stdout"]
                print(f'{buf}{prompt}')
            except:
                pass
            print()
        if ev.type[0] == "board":
            try:
                buf = ev.data["output"]
                print(f'{buf}')
            except:
                pass
            print()
        if ev.type[0] == "msg":
            try:
                if "Flags" in ev.data["text"]:
                    print(remove_control_characters(ev.data["text"]))
                if "Parameters" in ev.data["text"]:
                    print(remove_control_characters(ev.data["text"]))
                print()
            except:
                pass

        oldtime = newtime


if __name__ == "__main__":
    main()

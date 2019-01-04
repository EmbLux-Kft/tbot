#!/usr/bin/env python3
# tbot, Embedded Automation Tool
# Copyright (C) 2018  Heiko Schocher
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
Generate a statistic jpg with gnuplot

"""
import sys
import re
import pathlib
import string
import logparser

def main() -> None:
    """Generate a statistic jpg."""

    try:
        filename = pathlib.Path(sys.argv[1])
        log = logparser.logfile(str(filename))
    except IndexError:
        sys.stderr.write(
            f"""\
\x1B[1mUsage: {sys.argv[0]} <logfile>\x1B[0m
"""
        )
        sys.exit(1)
    except OSError:
        sys.stderr.write(
            f"""\
\x1B[31mopen failed!\x1B[0m
\x1B[1mUsage: {sys.argv[0]} <logfile>\x1B[0m
"""
        )
        sys.exit(1)

    tc_list = []
    def _search_in_list(name):
        for el in tc_list:
            if el["name"] == name:
                return el

        return None

    def _add_to_list(name):
        newel = {"name" : name, "good" : 0, "bad" : 0}
        tc_list.append(newel)

    def gen_list(ev: logparser.LogEvent) -> str:
        """Generate list of tc statistic."""
        if ev.type == ["tc", "begin"]:
            newname = ev.data['name']
            eln = _search_in_list(newname)
            if eln == None:
                _add_to_list(newname)
            return ""

        elif ev.type == ["tc", "end"]:
            newname = ev.data['name']
            #print (" === TIME ", ev.data['duration'])

            el = _search_in_list(newname)
            if el == None:
                raise RuntimeError(newname + " not found")

            if ev.data["success"] == True:
                el["good"] = el["good"] + 1
            else:
                el["bad"] = el["bad"] + 1

            return ""

        return "End"

    tmp = "\n".join(map(gen_list, log)),
    print('Name\tFail\tOk\n')
    for el in tc_list:
        print(el["name"] + '\t' + str(el["bad"]) + '\t' + str(el["good"]))

if __name__ == "__main__":
    main()

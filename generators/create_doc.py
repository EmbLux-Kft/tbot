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
Generate rst file which can be converted for example in a pdf

"""
import sys
import re
import pathlib
import string
import logparser

def main() -> None:
    """
    Generate a doucmentation in rst format. You can convert it
    for example into pdf.

    ToDo:
    - How to make chapters generic
      (add tags into rst files ?)
    """

    try:
        filename = pathlib.Path(sys.argv[1])
        log = logparser.logfile(str(filename))
        rstpath = pathlib.Path(sys.argv[2])
    except IndexError:
        sys.stderr.write(
            f"""\
\x1B[1mUsage: {sys.argv[0]} <logfile> <path2rstfiles>\x1B[0m
"""
        )
        sys.exit(1)
    except OSError:
        sys.stderr.write(
            f"""\
\x1B[31mopen failed!\x1B[0m
\x1B[1mUsage: {sys.argv[0]} <logfile> <path2rstfiles>\x1B[0m
"""
        )
        sys.exit(1)

    def tbot_write_cmd(ev, cmd_written):
        #print (" === cmd ", ev.data["cmd"])
        #print (" === typ ", ev.type)
        res = ''
        if cmd_written == 0:
            res += "\n::\n\n"
        else:
            pass

        res += "\t$ " + ev.data["cmd"] + "\n"
        # now stdout output
        # remove ANSI escape sequences
        reasc = re.compile(r'\x1b[^m]*m')
        fix = reasc.sub('', ev.data["stdout"])
        line = "\t" + fix.replace("\n", "\n\t")
        res += line[:-1]

        cmd_written = cmd_written + 1
        return cmd_written, res

    def is_tag_in_list(tags, tagid):
        for t in tags:
            if tagid in t["tagid"]:
                return True
        return False

    def replace_tbot_tags(content, tags):
        # TODO
        # while TBOT is running create TBOT_ tags
        # for example TBOT_BOARD_NAME
        # json file or simple text ?
        # or integrate into log ?
        #
        # also find possibility for making chapters generic
        #
        for t in tags:
            old = t["tagid"]
            new = t["tagval"]
            if "fixlen" in old:
                if len(new) < len(old):
                    c = len(old) - len(new)
                    addstring = " " * c
                    new = new + addstring

            content = content.replace(old, new)
        # fix following underlines length
        # or fix underlines when found
        return content

    def write_file(ev, ending):
        fn = ev.data["docid"] + ending
        #print (" open file ", rstpath / fn)
        res = ''
        with open(rstpath / fn, mode="r") as f:
            res = f.read()
        return res

    def call_analyse(log, level, tags):
        #print(" ====== level ===== ", level)
        cmd_written = 0
        res = ''
        for ev in log:
            #print (" ===== ev ", ev)
            if ev.type == ["doc", "begin"]:
                res += write_file(ev, "_begin.rst")
                tags, ret, retlev = call_analyse(log, level + 1, tags)
                #print(" ====== tags ", tags)
                #print(" ==== ret ", ret)
                res += ret
                cmd_written = 0

            elif ev.type == ["doc", "end"]:
                # end
                # load content of rst end file and print
                #print (" ==== end ", ev.data["docid"])
                res += write_file(ev, "_end.rst")
                return tags, res, level - 1

            elif ev.type == ["doc", "cmd"]:
                # load content of rst end file and print
                #print (" ==== end ", ev.data["docid"])
                res += write_file(ev, "_cmd.rst")
                cmd_written = 0

            elif ev.type == ["doc", "tag"]:
                # add tag into tag list
                tagid = ev.data["tagid"]
                tagval = ev.data["tagval"]
                #if not tagid in tags:
                ret = is_tag_in_list(tags, tagid)
                if ret == False:
                    tags.append(ev.data)

            elif level > 0:
                # only add cmd output, if one docid is active
                #print (" ============================== ", ev.type)
                if "cmd" in ev.type:
                    cmd_written, ret = tbot_write_cmd(ev, cmd_written)
                    res += ret

        return tags, res, level

    #print("filename ", filename)
    #print("rstpath ", rstpath)

    tags = []
    tags, content, retlev = call_analyse(log, 0, tags)
    if len(tags) != 0:
        content = replace_tbot_tags(content, tags)

    print (content)
    print("\n")

if __name__ == "__main__":
    main()

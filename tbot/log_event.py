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

import time
import typing

from tbot import log
from tbot.log import u, c

__all__ = ("doc_begin", "doc_image", "doc_cmd", "doc_tag", "doc_end", "testcase_begin", "testcase_end", "command")

"""
    Documentation generator searchs for a "doc" "begin" event
    and searches for a file with name docid_begin.rst and writes
    the content to the output file. After start is found it then
    writes all log types "cmd" to output, until it finds an "end".
    Nested "begin" is possible.

    log types                                           output

    types != "doc"                                      none

    "doc", "begin", "docid" -> ? docid_begin.rst ->     content of docid_begin.rst
    "cmd"                                               "data" in cmd block"
    "cmd"                                               "data" in cmd block", added to the above
                                                        cmd block
    "doc", "begin", "docid" -> ? docid_begin.rst ->     content of docid_begin.rst
    "cmd"                                               "data" in cmd block
    "doc", "end", "docid" -> ? docid_end.rst ->         content of docid_end.rst
    "cmd"                                               "data" in cmd block
    "doc", "end", "docid" -> ? docid_end.rst ->         content of docid_end.rst

    "doc", "cmd", "docid" -> ? docid_cmd.rst ->         content of docid_cmd.rst

    types != "doc"                                      none


    "doc", "tag", "tagid" "tagval"                      replace in the resulting rst
                                                        file all "tagid" occurencies
                                                        with "tagval".
                                                        If tagid contains "fixlen",
                                                        to short "tagval" are filled up with
                                                        spaces.

    :param str docid: ID of the doc section
"""

def doc_begin(docid: str) -> None:
    """
    Log a doc ID beginning.
    
    :param str docid: ID of the doc section
    """
    log.EventIO(
        ["doc", "begin"],
        message=f"add doc begin {docid}",
        verbosity=log.Verbosity.CHANNEL,
        docid=docid,
    )

def doc_image(imagename: str) -> None:
    """
    insert image imagename into rst

    :param str imagename: name of the image which gets inserted into rst
    """
    log.EventIO(
        ["doc", "image"],
        message=f"add doc image {imagename}",
        verbosity=log.Verbosity.CHANNEL,
        imagename=imagename,
    )

def doc_cmd(docid: str) -> None:
    """
    Log a doc cmd ID event

    :param str docid: ID of the doc cmd
    """
    log.EventIO(
        ["doc", "cmd"],
        message=f"add doc cmd {docid}",
        verbosity=log.Verbosity.CHANNEL,
        docid=docid,
    )

def doc_tag(tagid: str, tagval: str) -> None:
    """
    Log a doc tag ID event

    :param str docid: ID of the doc tag
    """
    log.EventIO(
        ["doc", "tag"],
        message=f"add doc tag {tagid} {tagval}",
        verbosity=log.Verbosity.CHANNEL,
        tagid=tagid,
        tagval=tagval
    )

def doc_end(docid: str) -> None:
    """
    Log a doc ID end.

    :param str docid: ID of the doc section
    """
    log.EventIO(
        ["doc", "end"],
        message=f"add doc end {docid}",
        verbosity=log.Verbosity.CHANNEL,
        docid=docid,
    )

def testcase_begin(name: str) -> None:
    """
    Log a testcase's beginning.

    :param str name: Name of the testcase
    """
    log.EventIO(
        ["tc", "begin"],
        "Calling " + c(name).cyan.bold + " ...",
        verbosity=log.Verbosity.QUIET,
        name=name,
    )
    log.NESTING += 1


def testcase_end(
    name: str,
    duration: float,
    success: bool = True,
    skipped: typing.Optional[str] = None,
) -> None:
    """
    Log a testcase's end.

    :param float duration: Time passed while this testcase ran
    :param bool success: Whether the testcase succeeded
    :param str skipped: ``None`` if the testcase ran normally or a string (the
        reason) if it was skipped.  If a testcase was skipped, ``success`` is
        ignored.
    """
    if skipped is not None:
        message = c("Skipped").yellow.bold + f": {skipped}"
        skip_info = {"skip_reason": skipped}
    else:
        # Testcase ran normally
        skip_info = {}
        if success:
            message = c("Done").green.bold + f". ({duration:.3f}s)"
        else:
            message = c("Fail").red.bold + f". ({duration:.3f}s)"

    log.EventIO(
        ["tc", "end"],
        message,
        nest_first=u("└─", "\\-"),
        verbosity=log.Verbosity.QUIET,
        name=name,
        duration=duration,
        success=success,
        skipped=skipped is not None,
        **skip_info,
    )
    log.NESTING -= 1


# Table which maps each control character to its unicode symbol from the
# "Control Picture" block.
_CONTROL_MAPPING = {c: 0x2400 + c for c in range(32)}


def command(mach: str, cmd: str) -> log.EventIO:
    """
    Log a command's execution.

    :param str mach: Name of the machine the command is run on
    :param str cmd: The command itself
    :rtype: EventIO
    :returns: A stream that the output of the command should
        be written to.
    """

    # Replace all newlines and other special characters in the command string
    if log.IS_UNICODE:
        cmd = cmd.translate(_CONTROL_MAPPING)

    ev = log.EventIO(
        ["cmd", mach],
        "[" + c(mach).yellow + "] " + c(cmd).dark,
        verbosity=log.Verbosity.COMMAND,
        cmd=cmd,
    )

    if log.INTERACTIVE:
        if input(ev._prefix() + c("  OK [Y/n]? ").magenta).upper() not in ("", "Y"):
            raise RuntimeError("Aborted by user")

    ev.prefix = "   ## "
    ev.verbosity = log.Verbosity.STDOUT
    return ev


def tbot_start() -> None:
    print(log.c("tbot").yellow.bold + " starting ...")
    log.NESTING += 1


def tbot_end(success: bool) -> None:
    log.message(
        log.c(
            log.u(
                "────────────────────────────────────────",
                "----------------------------------------",
            )
        ).dark
    )

    if log.LOGFILE is not None:
        log.message(f"Log written to {log.LOGFILE.name!r}")

    msg = log.c("SUCCESS").green.bold if success else log.c("FAILURE").red.bold
    duration = time.monotonic() - log.START_TIME
    log.EventIO(
        ["tbot", "end"],
        msg + f" ({duration:.3f}s)",
        nest_first=log.u("└─", "\\-"),
        verbosity=log.Verbosity.QUIET,
        success=success,
        duration=duration,
    )


def exception(name: str, trace: str) -> log.EventIO:
    ev = log.EventIO(
        ["exception"],
        log.c("Exception").red.bold + ":",
        verbosity=log.Verbosity.QUIET,
        name=name,
        trace=trace,
    )

    ev.prefix = "  "
    ev.write(trace)

    return ev

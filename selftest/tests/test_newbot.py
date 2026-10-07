import pathlib
import subprocess
import io
import json
import sys
from typing import Any

import tbot
import tbot.log
import tbot.log_event
import tbot.newbot  # noqa: F401

# TODO: Write tests...


def test_tbot_start_is_logged(capsys: Any) -> None:
    logfile, nesting = tbot.log.LOGFILE, tbot.log.NESTING
    tbot.log.LOGFILE = io.StringIO()
    tbot.log.NESTING = -1
    try:
        tbot.log_event.tbot_start(["-f", "flag", "tc"])
        ev = json.loads(tbot.log.LOGFILE.getvalue())
        assert tbot.log.NESTING == 0
    finally:
        tbot.log.LOGFILE, tbot.log.NESTING = logfile, nesting

    assert ev["type"] == ["tbot", "begin"]
    assert ev["data"]["argv"][0] == sys.modules["__main__"].__file__
    assert ev["data"]["argv"][1:] == ["-f", "flag", "tc"]
    assert len(ev["data"]["date"]) == len("2026-10-06 12:00:00")
    # printed as before, without a tree prefix
    assert capsys.readouterr().out.endswith("starting ...\n")


def test_flags_are_set_for_completion(tmp_path: pathlib.Path) -> None:
    # a testcase module may decide with flags which testcases it has
    (tmp_path / "flagtcs.py").write_text(
        "import tbot\n\n"
        'if "myflag" in tbot.flags:\n\n'
        "    def flagged_tc() -> None:\n"
        "        pass\n"
    )
    res = subprocess.run(
        [
            sys.executable,
            "-c",
            "import sys, tbot.newbot; tbot.newbot.main(sys.argv[1:])",
            "-C",
            str(tmp_path),
            "-f",
            "myflag",
            "--complete-testcase",
            "flagtcs.f",
        ],
        capture_output=True,
        text=True,
        cwd=pathlib.Path(__file__).parents[2],
    )
    assert "flagtcs.flagged_tc" in res.stdout.split(), res.stdout + res.stderr

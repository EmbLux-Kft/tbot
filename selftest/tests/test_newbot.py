import io
import json
import os
import pathlib
import sys
import traceback
from typing import Any, Callable, NamedTuple, Optional, Tuple

import pytest

import tbot
import tbot.log
import tbot.log_event
from tbot import newbot


class NewbotResult(NamedTuple):
    returncode: int
    stdout: str
    stderr: str


NewbotMain = Callable[..., NewbotResult]


@pytest.fixture
def newbot_main(monkeypatch: Any, capsys: Any) -> NewbotMain:
    """
    Call newbot.main() in this process, so that the coverage of the selftest
    includes it.  monkeypatch restores what main() changes: sys.path, the
    working directory, tbot.flags, tbot.ctx and the log settings.
    """

    def run(tcdir: pathlib.Path, *args: str) -> NewbotResult:
        monkeypatch.setattr(sys, "path", list(sys.path))
        monkeypatch.chdir(os.getcwd())
        monkeypatch.setattr(tbot, "flags", set())
        monkeypatch.setattr(tbot, "ctx", tbot.ctx)
        for name in ("VERBOSITY", "LOGFILE", "NESTING"):
            monkeypatch.setattr(tbot.log, name, getattr(tbot.log, name))
        # the testcase modules of tcdir are imported anew for every run
        for name, mod in list(sys.modules.items()):
            if str(getattr(mod, "__file__", "") or "").startswith(str(tcdir)):
                monkeypatch.delitem(sys.modules, name)

        capsys.readouterr()
        returncode = 0
        try:
            newbot.main(["-C", str(tcdir), *args])
        except SystemExit as e:
            returncode = e.code if isinstance(e.code, int) else 1
        except Exception:
            # main() raises the exception of a failed run; a subprocess would
            # print it and exit with 1
            traceback.print_exc()
            returncode = 1
        out = capsys.readouterr()
        return NewbotResult(returncode, out.out, out.err)

    return run


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


# Testcase parameters {{{
TESTCASES = """\
from __future__ import annotations

from typing import Optional

import tbot


@tbot.testcase
def ping(host: str = "localhost", count: int = 1) -> None:
    print("ping", repr(host), repr(count))


@tbot.testcase
def label(name: Optional[str] = "x", ratio: float = 0.5, raw=None) -> None:
    print("label", repr(name), repr(ratio), repr(raw))


def kw(**kwargs) -> None:
    print("kw", sorted(kwargs.items()))


@tbot.testcase
def other() -> None:
    print("other")


def unresolvable(n: NoSuchType = 1) -> None:  # noqa: F821
    print("unresolvable", repr(n))
"""


@pytest.fixture
def tcdir(tmp_path: pathlib.Path) -> pathlib.Path:
    (tmp_path / "tcs.py").write_text(TESTCASES)
    return tmp_path


@pytest.fixture
def tcs(tcdir: pathlib.Path, monkeypatch: Any) -> pathlib.Path:
    monkeypatch.syspath_prepend(str(tcdir))
    monkeypatch.delitem(sys.modules, "tcs", raising=False)
    return tcdir


@pytest.mark.parametrize(  # type: ignore
    "arg,expected",
    [
        ("count=3", ("count", "3")),
        ("opts=a=b", ("opts", "a=b")),
        ("empty=", ("empty", "")),
    ],
)
def test_parse_param(arg: str, expected: Tuple[str, str]) -> None:
    assert newbot.parse_param(arg) == expected


@pytest.mark.parametrize("arg", ["novalue", "=1", "1x=2", "a-b=1"])  # type: ignore
def test_parse_param_invalid(arg: str) -> None:
    with pytest.raises(ValueError, match="expected NAME=VALUE"):
        newbot.parse_param(arg)


def test_parse_params_twice() -> None:
    with pytest.raises(ValueError, match="given twice"):
        newbot.parse_params(["a=1", "a=2"])


@pytest.mark.parametrize(  # type: ignore
    "value,expected",
    [
        ("42", 42),
        ("1.5", 1.5),
        ("True", True),
        ("None", None),
        ("[1, 'a']", [1, "a"]),
        ("{'a': 1}", {"a": 1}),
        ("'42'", "42"),
        ("eth0", "eth0"),
        ("hello world", "hello world"),
        ("010", "010"),
        ("__import__('os').system('false')", "__import__('os').system('false')"),
    ],
)
def test_convert_param_literal(value: str, expected: Any) -> None:
    assert newbot.convert_param(value) == expected


@pytest.mark.parametrize(  # type: ignore
    "value,annotation,expected",
    [
        ("1234", str, "1234"),
        ("None", str, "None"),
        ("1234", Optional[str], "1234"),
        ("None", Optional[str], None),
        ("3", int, 3),
        ("1", float, 1),
        ("2.5", float, 2.5),
        ("False", bool, False),
    ],
)
def test_convert_param_annotated(value: str, annotation: Any, expected: Any) -> None:
    result = newbot.convert_param(value, annotation)
    assert result == expected and type(result) is type(expected)


@pytest.mark.parametrize(  # type: ignore
    "value,annotation",
    [("abc", int), ("True", int), ("1.5", int), ("1", bool), ("x", float)],
)
def test_convert_param_wrong_type(value: str, annotation: Any) -> None:
    with pytest.raises(ValueError, match=f"expected {annotation.__name__}"):
        newbot.convert_param(value, annotation)


def test_testcase_call_parse() -> None:
    call = newbot.TestcaseCall.parse("tc.net.ping")
    assert call == newbot.TestcaseCall("tc.net.ping")
    call = newbot.TestcaseCall.parse("tc.net.get:url=http://h:8080/x:retries=2")
    assert call.name == "tc.net.get"
    assert call.params == {"url": "http://h:8080/x", "retries": "2"}


@pytest.mark.parametrize(  # type: ignore
    "arg", ["ping", "tc.net.ping:", "tc.net.ping:3", "tc.net.ping:a b=1"]
)
def test_testcase_call_parse_invalid(arg: str) -> None:
    with pytest.raises(ValueError, match="invalid testcase"):
        newbot.TestcaseCall.parse(arg)


def test_resolve_converts_by_annotation(tcs: pathlib.Path) -> None:
    # tcs.py uses "from __future__ import annotations", so the annotations
    # are strings and come from typing.get_type_hints().
    call = newbot.TestcaseCall.parse("tcs.ping:host=1234:count=3")
    assert call.resolve({}) == []
    assert call.kwargs == {"host": "1234", "count": 3}

    call = newbot.TestcaseCall.parse("tcs.label:name=None:ratio=2:raw=[1]")
    call.resolve({})
    assert call.kwargs == {"name": None, "ratio": 2, "raw": [1]}


def test_resolve_global_params(tcs: pathlib.Path) -> None:
    call = newbot.TestcaseCall.parse("tcs.ping:count=2")
    assert call.resolve({"count": "5", "name": "a"}) == ["name"]
    # the parameter given for the testcase wins over -p
    assert call.kwargs == {"count": 2}

    call = newbot.TestcaseCall.parse("tcs.kw")
    assert call.resolve({"count": "5"}) == []
    assert call.kwargs == {"count": 5}


def test_resolve_unknown_param(tcs: pathlib.Path) -> None:
    with pytest.raises(TypeError, match="has no parameter `hots`"):
        newbot.TestcaseCall.parse("tcs.ping:hots=a").resolve({})


def test_resolve_wrong_type(tcs: pathlib.Path) -> None:
    with pytest.raises(ValueError, match="parameter `count` of `tcs.ping\\(\\)`"):
        newbot.TestcaseCall.parse("tcs.ping:count=many").resolve({})


def test_newbot_params(newbot_main: NewbotMain, tcdir: pathlib.Path) -> None:
    res = newbot_main(
        tcdir,
        "-p",
        "count=5",
        "tcs.ping:host=10.0.0.1:count=3",
        "tcs.ping",
        "tcs.other",
    )
    assert res.returncode == 0, res.stdout + res.stderr
    assert "ping '10.0.0.1' 3" in res.stdout
    assert "ping 'localhost' 5" in res.stdout
    assert "Parameter 'count' not defined for testcase 'tcs.other'" in res.stdout
    assert "other" in res.stdout


def test_newbot_checks_all_before_running(
    newbot_main: NewbotMain, tcdir: pathlib.Path
) -> None:
    res = newbot_main(tcdir, "tcs.other", "tcs.ping:hots=10.0.0.1")
    assert res.returncode != 0
    assert "has no parameter `hots`" in res.stdout + res.stderr
    assert "other\n" not in res.stdout


def test_newbot_param_of_no_testcase(
    newbot_main: NewbotMain, tcdir: pathlib.Path
) -> None:
    res = newbot_main(tcdir, "-p", "cuont=3", "tcs.ping", "tcs.other")
    assert res.returncode != 0
    assert "no testcase has the parameter `cuont`" in res.stdout + res.stderr


@pytest.mark.parametrize(  # type: ignore
    "args", [("-p", "count", "tcs.ping"), ("tcs.ping:count=1:count=2",)]
)
def test_newbot_malformed_param_is_usage_error(
    newbot_main: NewbotMain, tcdir: pathlib.Path, args: Tuple[str, ...]
) -> None:
    res = newbot_main(tcdir, *args)
    assert res.returncode == 2
    assert "usage:" in res.stderr


def test_newbot_logs_start_and_parameters(
    newbot_main: NewbotMain, tcdir: pathlib.Path
) -> None:
    log = tcdir / "log.json"
    res = newbot_main(tcdir, "--json-log-stream", str(log), "tcs.ping:count=2")
    assert res.returncode == 0, res.stdout + res.stderr
    assert "Parameters of tcs.ping" in res.stdout
    # the log is a sequence of indented JSON objects
    text, pos, events = log.read_text(), 0, []
    decoder = json.JSONDecoder()
    while text[pos:].strip():
        ev, pos = decoder.raw_decode(text, len(text) - len(text[pos:].lstrip()))
        events.append(ev)
    assert events[0]["type"] == ["tbot", "begin"]
    assert events[0]["data"]["argv"][-1] == "tcs.ping:count=2"
    assert events[-1]["type"] == ["tbot", "end"]
    assert events[-1]["data"]["success"]


def test_newbot_wrong_parameter_value(
    newbot_main: NewbotMain, tcdir: pathlib.Path
) -> None:
    res = newbot_main(tcdir, "tcs.label:ratio=x")
    assert res.returncode == 1
    assert "expected float" in res.stdout + res.stderr


def test_run_testcase(tcs: pathlib.Path, capsys: Any) -> None:
    newbot.run_testcase("tcs.ping:host=h:count=2")
    assert "ping 'h' 2" in capsys.readouterr().out


def test_resolve_no_such_function(tcs: pathlib.Path) -> None:
    with pytest.raises(AttributeError, match="does not contain `nosuch"):
        newbot.TestcaseCall.parse("tcs.nosuch").resolve({})


def test_resolve_unresolvable_annotation(tcs: pathlib.Path) -> None:
    call = newbot.TestcaseCall.parse("tcs.unresolvable:n=3")
    call.resolve({})
    assert call.kwargs == {"n": 3}


def test_complete_testcase_stops_at_params() -> None:
    assert list(newbot.complete_testcase("tbot.tc.selftest:x=")) == []


# }}}


def test_flags_are_set_for_completion(
    newbot_main: NewbotMain, tmp_path: pathlib.Path
) -> None:
    # a testcase module may decide with flags which testcases it has
    (tmp_path / "flagtcs.py").write_text(
        "import tbot\n\n"
        'if "myflag" in tbot.flags:\n\n'
        "    def flagged_tc() -> None:\n"
        "        pass\n"
    )
    res = newbot_main(tmp_path, "-f", "myflag", "--complete-testcase", "flagtcs.f")
    assert "flagtcs.flagged_tc" in res.stdout.split(), res.stdout + res.stderr

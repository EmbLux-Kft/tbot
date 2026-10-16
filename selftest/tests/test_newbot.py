import pathlib
import sys
from typing import Any, Optional, Tuple

import pytest

from tbot import newbot


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


def test_resolve_testcases_param_of_no_testcase(tcs: pathlib.Path) -> None:
    calls = [
        newbot.TestcaseCall.parse("tcs.ping"),
        newbot.TestcaseCall.parse("tcs.other"),
    ]
    with pytest.raises(TypeError, match="no testcase has the parameter `cuont`"):
        newbot.resolve_testcases(calls, {"cuont": "3"})


def test_resolve_testcases_ignores_param_where_missing(tcs: pathlib.Path) -> None:
    calls = [
        newbot.TestcaseCall.parse("tcs.ping"),
        newbot.TestcaseCall.parse("tcs.other"),
    ]
    newbot.resolve_testcases(calls, {"count": "3"})
    assert calls[0].kwargs == {"count": 3}
    assert calls[1].kwargs == {}


def test_complete_testcase_stops_at_params() -> None:
    assert list(newbot.complete_testcase("tbot.tc.selftest:x=")) == []

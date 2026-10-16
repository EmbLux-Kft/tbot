#!/usr/bin/env python3
# SPDX-License-Identifier: GPL-3.0-or-later
import argparse
import ast
import dataclasses
import importlib
import inspect
import itertools
import os
import pathlib
import re
import string
import sys
import typing
from typing import Any, Callable, Dict, Iterable, List, Optional, Sequence, Tuple

if typing.TYPE_CHECKING:
    import tbot


def load_config(config: str, ctx: "tbot.Context") -> None:
    args: Sequence[Optional[str]]

    config_name, *args = config.split(":")
    config_module = importlib.import_module(config_name)

    # Replace empty args with `None`
    args = [(arg if arg != "" else None) for arg in args]

    if not hasattr(config_module, "register_machines"):
        raise AttributeError(f"{config_name} is missing `register_machines()`")

    getattr(config_module, "register_machines")(ctx, *args)


# Parameters of a testcase on the command line start at a ":" followed by
# "NAME=", so a value may contain colons itself (URLs, host:port, ...).
_PARAM_START = re.compile(r":(?=[A-Za-z_][A-Za-z0-9_]*=)")


def parse_param(arg: str) -> Tuple[str, str]:
    """Split a ``NAME=VALUE`` testcase parameter into name and value."""
    name, sep, value = arg.partition("=")
    if sep == "" or not name.isidentifier():
        raise ValueError(f"invalid testcase parameter {arg!r}, expected NAME=VALUE")
    return name, value


def parse_params(args: Iterable[str]) -> Dict[str, str]:
    """Parse ``NAME=VALUE`` testcase parameters, each name only once."""
    params: Dict[str, str] = {}
    for arg in args:
        name, value = parse_param(arg)
        if name in params:
            raise ValueError(f"testcase parameter {name!r} given twice")
        params[name] = value
    return params


def _wants_str(annotation: Any) -> bool:
    if annotation is str:
        return True
    if typing.get_origin(annotation) is typing.Union:
        return str in typing.get_args(annotation)
    return False


def convert_param(value: str, annotation: Any = inspect.Parameter.empty) -> Any:
    """
    Convert the value of a testcase parameter from the command line.

    A parameter annotated as ``str`` gets the value unchanged.  So does one
    annotated as a ``Union`` containing ``str`` (like ``Optional[str]``),
    except that ``None`` becomes ``None`` there.  For all other parameters
    the value is read as a Python literal (``42``, ``1.5``, ``True``,
    ``None``, ``"text"``, ``[1, 2]``, ``{"a": 1}``) with
    :py:func:`ast.literal_eval`, and a value that is no literal stays a
    string.  The value is never run as code.

    A parameter annotated as ``bool``, ``int`` or ``float`` must get a value
    of that type (an ``int`` is fine for a ``float``).
    """
    if _wants_str(annotation):
        if annotation is not str and value == "None":
            return None
        return value

    try:
        result = ast.literal_eval(value)
    except (ValueError, SyntaxError, TypeError, MemoryError, RecursionError):
        result = value

    if annotation in (bool, int, float):
        allowed = (int, float) if annotation is float else (annotation,)
        is_bool = isinstance(result, bool)
        if not isinstance(result, allowed) or (is_bool and annotation is not bool):
            raise ValueError(f"expected {annotation.__name__}, got {value!r}")

    return result


@dataclasses.dataclass
class TestcaseCall:
    """A testcase from the command line and the parameters given for it."""

    name: str
    """Testcase as ``module.function``."""

    params: Dict[str, str] = dataclasses.field(default_factory=dict)
    """Parameters from ``module.function:NAME=VALUE``, not yet converted."""

    func: Optional[Callable[..., Any]] = None
    """Testcase function, set by :py:meth:`resolve`."""

    kwargs: Dict[str, Any] = dataclasses.field(default_factory=dict)
    """Converted keyword arguments of the call, set by :py:meth:`resolve`."""

    @classmethod
    def parse(cls, arg: str) -> "TestcaseCall":
        """Parse ``module.function[:NAME=VALUE...]``."""
        name, *params = _PARAM_START.split(arg)
        if ":" in name or "." not in name:
            raise ValueError(
                f"invalid testcase {arg!r}, expected module.function[:NAME=VALUE...]"
            )
        return cls(name, parse_params(params))

    def resolve(self, global_params: Dict[str, str]) -> List[str]:
        """
        Import the testcase and build the keyword arguments of the call.

        Every parameter given for this testcase must be a parameter of the
        testcase function.  Of the ``-p`` parameters (``global_params``),
        those the function does not have are left out, and their names are
        returned.
        """
        module_name, function_name = self.name.rsplit(".", 1)
        module = importlib.import_module(module_name)

        if not hasattr(module, function_name):
            raise AttributeError(
                f"`{module_name}` does not contain `{function_name}()`"
            )
        self.func = getattr(module, function_name)

        # inspect.signature() follows __wrapped__ to the testcase function
        # below the decorators.
        sig = inspect.signature(self.func)
        try:
            hints = typing.get_type_hints(inspect.unwrap(self.func))
        except Exception:
            hints = {}

        def accepts(name: str) -> bool:
            p = sig.parameters.get(name)
            if p is not None:
                return p.kind in (p.POSITIONAL_OR_KEYWORD, p.KEYWORD_ONLY)
            return any(p.kind == p.VAR_KEYWORD for p in sig.parameters.values())

        unknown = [name for name in self.params if not accepts(name)]
        if unknown:
            raise TypeError(
                f"`{self.name}()` has no parameter "
                + ", ".join(f"`{name}`" for name in unknown)
            )
        ignored = [name for name in global_params if not accepts(name)]

        params = {k: v for k, v in global_params.items() if k not in ignored}
        params.update(self.params)

        self.kwargs = {}
        for name, value in params.items():
            p = sig.parameters.get(name)
            annotation = p.annotation if p is not None else inspect.Parameter.empty
            try:
                self.kwargs[name] = convert_param(value, hints.get(name, annotation))
            except ValueError as e:
                raise ValueError(
                    f"parameter `{name}` of `{self.name}()`: {e}"
                ) from None

        return ignored

    def run(self) -> None:
        """Call the testcase, :py:meth:`resolve` must have been called."""
        assert self.func is not None, "resolve() was not called"
        if self.kwargs:
            import tbot.log

            tbot.log.message(
                tbot.log.c(f"Parameters of {self.name}: ").bold
                + ", ".join(f"{k}={v!r}" for k, v in self.kwargs.items())
            )
        self.func(**self.kwargs)


def resolve_testcases(
    calls: Sequence[TestcaseCall], global_params: Dict[str, str]
) -> None:
    """
    Resolve all testcases before the first one runs, so that a wrong
    parameter is reported before anything happens on a machine.

    A ``-p`` parameter that no testcase has is an error.  One that only
    some testcases have is left out for the others, with a warning.
    """
    import tbot.log

    ignored = {call.name: call.resolve(global_params) for call in calls}

    for name in global_params:
        if calls and all(name in names for names in ignored.values()):
            raise TypeError(f"no testcase has the parameter `{name}` given with -p")

    for tc, names in ignored.items():
        for name in names:
            tbot.log.warning(
                f"Parameter {name!r} not defined for testcase {tc!r}, ignoring ..."
            )


def run_testcase(testcase: str) -> None:
    """Run a testcase given as ``module.function[:NAME=VALUE...]``."""
    call = TestcaseCall.parse(testcase)
    call.resolve({})
    call.run()


def complete_module(cur: str) -> Iterable[str]:
    # There are already arguments being passed now - nothing to complete anymore.
    if ":" in cur:
        return ()

    components = cur.rsplit(".", 1)
    if len(components) == 2:
        modpath = components[0] + "."
        path = pathlib.Path(components[0].replace(".", "/"))
        frag = components[1]
    else:
        modpath = ""
        path = pathlib.Path(".")
        frag = components[0]

    # If the module directory is missing, we won't find anything so return
    # early.
    if not path.is_dir():
        return ()

    # If the fragment already marks an existing submodule, we can complete
    # inside it instead.  Append it to the path, as if a trailing `.` was
    # passed.
    if frag != "" and (path / frag).is_dir():
        modpath += frag + "."
        path = path / frag
        frag = ""

    # Collect all subdirectories and python script files as potential module
    # names.
    candidates = []
    for child in path.iterdir():
        if child.name.startswith(frag) and not child.name.startswith("__"):
            if child.is_dir():
                candidates.append(child.name)
            elif child.is_file() and child.suffix == ".py":
                candidates.append(child.stem)

    return (modpath + c for c in sorted(candidates))


def complete_testcase(cur: str) -> Iterable[str]:
    # The parameters of the testcase follow, nothing to complete anymore.
    if ":" in cur:
        return ()

    components = cur.rsplit(".", 1)
    if len(components) == 1:
        return complete_module(cur)

    modpath = components[0]
    path = pathlib.Path(components[0].replace(".", "/"))
    frag = components[1]

    if frag != "" and (path / frag).with_suffix(".py").is_file():
        path = path / frag
        modpath += "." + frag
        frag = ""

    if not path.with_suffix(".py").is_file() and not (path / "__init__.py").is_file():
        return complete_module(cur)

    module = importlib.import_module(modpath)
    callables = (f for f in dir(module) if callable(getattr(module, f, None)))
    matching = (modpath + "." + f for f in callables if f.startswith(frag))

    if path.is_dir():
        matching_mods = complete_module(cur)
        return itertools.chain(matching_mods, matching)
    else:
        return matching


def get_version() -> str:
    try:
        from importlib import metadata  # type: ignore

        try:
            return metadata.version("tbot")  # type: ignore
        except metadata.PackageNotFoundError:  # type: ignore
            pass
    except ImportError:
        pass

    try:
        from tbot import _version  # type: ignore

        return _version.version  # type: ignore
    except ImportError:
        pass

    return "unknown"


def build_parser() -> argparse.ArgumentParser:
    parser = TbotArgumentParser(
        prog="tbot",
        description="Test and development automation tool, tailored for embedded"
        + " (experimental new CLI)",
        fromfile_prefix_chars="@",
    )

    parser.add_argument(
        "-C",
        metavar="WORKDIR",
        dest="workdir",
        help="use WORKDIR as working directory instead of the current directory.",
    )

    parser.add_argument("-b", "--board", help="alias for `-c`")
    parser.add_argument("-l", "--lab", help="alias for `-c`")
    parser.add_argument("-c", "--config", action="append", default=[])

    parser.add_argument(
        "-f",
        metavar="FLAG",
        dest="flags",
        action="append",
        default=[],
        help="set a user defined flag to change testcase behaviour",
    )

    parser.add_argument(
        "-p",
        "--param",
        metavar="NAME=VALUE",
        dest="params",
        action="append",
        default=[],
        help="pass a parameter to every testcase that has it; VALUE is a Python"
        + " literal or else a string (per testcase: module.function:NAME=VALUE)",
    )

    parser.add_argument(
        "-k",
        "--keep-alive",
        dest="keep_alive",
        action="store_true",
        default=False,
        help="keep machines alive for later tests to reacquire them",
    )

    parser.add_argument(
        "--json-log-stream", metavar="LOGFILE", help="write a log to the specified file"
    )

    parser.add_argument(
        "-v", dest="verbosity", action="count", default=0, help="increase the verbosity"
    )

    parser.add_argument(
        "-q", dest="quiet", action="count", default=0, help="decrease the verbosity"
    )

    parser.add_argument(
        "--version", action="version", version=f"%(prog)s {get_version()}"
    )

    parser.add_argument(
        "testcase",
        nargs="*",
        help="testcase that should be run, as module.function[:NAME=VALUE...]",
    )

    return parser


class TbotArgumentParser(argparse.ArgumentParser):
    def convert_arg_line_to_args(self, arg_line: str) -> List[str]:
        """
        Make it possible to use shell variables also in argumentsfiles.
        """
        try:
            arg_line_expanded = string.Template(arg_line).substitute(os.environ)
        except KeyError as e:
            raise tbot.error.TbotException(
                f"Could not find environment variable: {e.args[0]!r}"
            ) from None

        return [arg_line_expanded]


def main(argv: Optional[Sequence[str]] = None) -> None:
    parser = build_parser()

    parser.add_argument("--complete-module", help=argparse.SUPPRESS)
    parser.add_argument("--complete-testcase", help=argparse.SUPPRESS)

    args = parser.parse_args(argv)

    try:
        global_params = parse_params(args.params)
        calls = [TestcaseCall.parse(tc) for tc in args.testcase]
    except ValueError as e:
        parser.error(str(e))

    if args.workdir:
        os.chdir(args.workdir)

    # Make sure the directory we're running from is available
    sys.path.insert(1, os.getcwd())

    import tbot

    for flag in args.flags:
        tbot.flags.add(flag)

    try:
        if args.complete_module is not None:
            for compl in complete_module(args.complete_module):
                print(compl)
            return

        if args.complete_testcase is not None:
            for compl in complete_testcase(args.complete_testcase):
                print(compl)
            return
    except Exception:
        # Silently drop these exceptions to not disturb commandline completion
        sys.exit(1)

    import tbot.log
    import tbot.log_event

    if args.json_log_stream:
        tbot.log.LOGFILE = open(args.json_log_stream, "w")

    tbot.log.VERBOSITY = tbot.log.Verbosity(
        tbot.log.Verbosity.STDOUT + args.verbosity - args.quiet
    )

    tbot.log_event.tbot_start(sys.argv[1:] if argv is None else argv)

    # Initialize tbot context with our settings
    tbot.ctx = tbot.Context(add_defaults=True, keep_alive=args.keep_alive)

    if args.lab is not None:
        load_config(args.lab, tbot.ctx)
    if args.board is not None:
        load_config(args.board, tbot.ctx)
    for config in args.config:
        load_config(config, tbot.ctx)

    try:
        resolve_testcases(calls, global_params)
        with tbot.ctx:
            for call in calls:
                call.run()
    except Exception as e:
        import traceback

        trace = traceback.format_exc(limit=-6)
        tbot.log_event.exception(e.__class__.__name__, trace)
        tbot.log_event.tbot_end(False)
        raise e
    except KeyboardInterrupt:
        tbot.log_event.exception("KeyboardInterrupt", "Test run manually aborted.")
        tbot.log_event.tbot_end(False)
        raise 130
    except SystemExit as e:
        tbot.log.message("SystemExit triggered.")
        tbot.log_event.tbot_end(e.code in (None, 0))
        raise e
    else:
        tbot.log_event.tbot_end(True)


if __name__ == "__main__":
    sys.exit(main(sys.argv))

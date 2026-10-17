"""
A small pytest for the app's Python.

The parts of pytest a learner meets: test discovery (`test_*.py` files, `test*` functions and
methods of `Test*` classes), a failed `assert` reported with the values it compared,
`pytest.raises`, `approx`, `fail` and `skip`, fixtures (with `yield`, `conftest.py`, and the
built-in `tmp_path`, `capsys` and `monkeypatch`), `mark.parametrize`, `skip`, `skipif` and
`xfail`, and the options -q, -v, -x, -s and -k. The same tests pass and fail as under pytest, and
the report reads the same, only narrower: a phone's terminal is about forty characters wide.
There are no plugins or configuration files.
"""

import builtins
import contextlib
import importlib
import importlib.util
import inspect
import io
import itertools
import math
import os
import pathlib
import re
import shutil
import sys
import tempfile
import time
import traceback
from collections import namedtuple

from _runner import explain

WIDTH = 40

__all__ = ["approx", "fail", "fixture", "main", "mark", "param", "raises", "skip", "xfail"]


# ---- outcomes -------------------------------------------------------------------------------


class OutcomeException(BaseException):
    """Ends a test with an outcome. Not an Exception: `except Exception` does not catch it."""

    def __init__(self, msg=None):
        super().__init__(msg)
        self.msg = msg

    def __str__(self):
        return self.msg or ""


class Failed(OutcomeException):
    pass


class Skipped(OutcomeException):
    pass


class XFailed(Failed):
    pass


def fail(reason="", pytrace=True):
    raise Failed(reason)


def skip(reason="", *, allow_module_level=False):
    raise Skipped(reason)


def xfail(reason=""):
    raise XFailed(reason)


fail.Exception = Failed
skip.Exception = Skipped
xfail.Exception = XFailed


# ---- raises ---------------------------------------------------------------------------------


class ExceptionInfo:
    """What `raises` caught: `.type`, `.value`, `.typename`, `.match(pattern)`."""

    def __init__(self):
        self.type = self.value = self.tb = None

    @property
    def typename(self):
        return self.type.__name__

    def match(self, regexp):
        text = str(self.value)
        if not re.search(regexp, text):
            fail(f"Regex pattern did not match.\n Regex: {regexp!r}\n Input: {text!r}")
        return True

    def __repr__(self):
        if self.type is None:
            return "<ExceptionInfo for raises contextmanager>"
        return f"<ExceptionInfo {self.type.__name__}({self.value!r})>"


class RaisesContext:
    def __init__(self, expected, match):
        self.expected = expected
        self.match = match
        self.info = ExceptionInfo()

    def __enter__(self):
        return self.info

    def __exit__(self, kind, value, tb):
        if kind is None:
            fail(f"DID NOT RAISE {self.expected}")
        if not issubclass(kind, self.expected):
            return False
        self.info.type, self.info.value, self.info.tb = kind, value, tb
        if self.match is not None:
            self.info.match(self.match)
        return True


def raises(expected_exception, *args, match=None, **kwargs):
    """`with pytest.raises(ValueError):` — the block must raise it; or `raises(E, func, *args)`."""
    if not args:
        return RaisesContext(expected_exception, match)
    func, *args = args
    with RaisesContext(expected_exception, match) as info:
        func(*args, **kwargs)
    return info


# ---- approx ---------------------------------------------------------------------------------


def _number(x):
    return isinstance(x, (int, float, complex)) and not isinstance(x, bool)


class ApproxBase:
    """A number, or a list, tuple or dict of numbers, compared with a tolerance."""

    def __init__(self, expected, rel=None, abs=None, nan_ok=False):
        self.expected, self.rel, self.abs, self.nan_ok = expected, rel, abs, nan_ok

    def _tolerance(self, e):
        absolute = 1e-12 if self.abs is None else self.abs
        if self.rel is None and self.abs is not None:
            return absolute
        return max((1e-6 if self.rel is None else self.rel) * builtins.abs(e), absolute)

    def _close(self, actual, e):
        if not (_number(e) and _number(actual)):
            return actual == e
        if actual == e:
            return True
        if isinstance(e, float) and math.isnan(e):
            return self.nan_ok and isinstance(actual, float) and math.isnan(actual)
        if math.isinf(builtins.abs(e)) or math.isinf(builtins.abs(actual)):
            return False
        return builtins.abs(actual - e) <= self._tolerance(e)

    def __eq__(self, actual):
        e = self.expected
        if isinstance(e, dict):
            return isinstance(actual, dict) and actual.keys() == e.keys() and all(self._close(actual[k], e[k]) for k in e)
        if isinstance(e, (list, tuple)):
            try:
                return len(actual) == len(e) and all(self._close(a, x) for a, x in zip(actual, e))
            except TypeError:
                return False
        return self._close(actual, e)

    __hash__ = None

    def _one(self, e):
        return f"{e!r} ± {self._tolerance(e):.1e}" if _number(e) else repr(e)

    def __repr__(self):
        e = self.expected
        if isinstance(e, dict):
            return "approx({" + ", ".join(f"{k!r}: {self._one(v)}" for k, v in e.items()) + "})"
        if isinstance(e, list):
            return "approx([" + ", ".join(self._one(x) for x in e) + "])"
        if isinstance(e, tuple):
            return "approx((" + ", ".join(self._one(x) for x in e) + "))"
        return self._one(e)


def approx(expected, rel=None, abs=None, nan_ok=False):
    """`0.1 + 0.2 == approx(0.3)`: equal within a relative tolerance of 1e-6."""
    return ApproxBase(expected, rel, abs, nan_ok)


# ---- marks ----------------------------------------------------------------------------------


Mark = namedtuple("Mark", "name args kwargs")


class MarkDecorator:
    def __init__(self, name, args=(), kwargs=None):
        self.mark = Mark(name, tuple(args), dict(kwargs or {}))

    @property
    def name(self):
        return self.mark.name

    def __call__(self, *args, **kwargs):
        if len(args) == 1 and not kwargs and (inspect.isfunction(args[0]) or inspect.isclass(args[0])):
            target = args[0]
            target.pytestmark = [*getattr(target, "pytestmark", []), self.mark]
            return target
        return MarkDecorator(self.mark.name, self.mark.args + args, {**self.mark.kwargs, **kwargs})


class MarkGenerator:
    """`pytest.mark.parametrize(...)`, `pytest.mark.skip`, any `pytest.mark.<name>`."""

    def __getattr__(self, name):
        if name.startswith("_"):
            raise AttributeError(name)
        return MarkDecorator(name)


mark = MarkGenerator()

ParameterSet = namedtuple("ParameterSet", "values marks id")


def param(*values, marks=(), id=None):
    """One case of `parametrize` with its own id or marks."""
    if isinstance(marks, MarkDecorator):
        marks = (marks,)
    return ParameterSet(values, tuple(m.mark if isinstance(m, MarkDecorator) else m for m in marks), id)


# ---- fixtures -------------------------------------------------------------------------------


def fixture(function=None, *, scope="function", params=None, autouse=False, ids=None, name=None):
    """`@pytest.fixture`: what a test receives by naming it as a parameter."""

    def register(fn):
        fn._pytestfixture = {"scope": scope, "autouse": autouse, "name": name or fn.__name__}
        return fn

    return register(function) if function is not None else register


CaptureResult = namedtuple("CaptureResult", "out err")


class _Capture:
    """A test's output: shown when the test fails, and read by `capsys`."""

    def __init__(self, enabled):
        self.enabled = enabled
        self.out, self.err = io.StringIO(), io.StringIO()
        self._stack = None

    def __enter__(self):
        if self.enabled:
            self._stack = contextlib.ExitStack()
            self._stack.enter_context(contextlib.redirect_stdout(self.out))
            self._stack.enter_context(contextlib.redirect_stderr(self.err))
        return self

    def __exit__(self, *exc):
        if self._stack:
            self._stack.close()
        return False

    def read(self):
        result = CaptureResult(self.out.getvalue(), self.err.getvalue())
        for stream in (self.out, self.err):
            stream.seek(0)
            stream.truncate()
        return result


class CaptureFixture:
    def __init__(self, capture):
        self._capture = capture

    def readouterr(self):
        return self._capture.read()


_NOTSET = object()


class MonkeyPatch:
    """Changes undone after the test: attributes, dict items, environment variables."""

    def __init__(self):
        self._undo = []

    def setattr(self, target, name, value=_NOTSET, raising=True):
        if value is _NOTSET:
            if not isinstance(target, str):
                raise TypeError("use setattr(target, name, value) or setattr('module.name', value)")
            module, _, attr = target.rpartition(".")
            target, name, value = importlib.import_module(module), attr, name
        old = getattr(target, name, _NOTSET)
        if raising and old is _NOTSET:
            raise AttributeError(f"{target!r} has no attribute {name!r}")
        self._undo.append(lambda: setattr(target, name, old) if old is not _NOTSET else delattr(target, name))
        setattr(target, name, value)

    def delattr(self, target, name=_NOTSET, raising=True):
        if name is _NOTSET:
            module, _, name = target.rpartition(".")
            target = importlib.import_module(module)
        old = getattr(target, name, _NOTSET)
        if old is _NOTSET:
            if raising:
                raise AttributeError(name)
            return
        self._undo.append(lambda: setattr(target, name, old))
        delattr(target, name)

    def setitem(self, dic, name, value):
        old = dic.get(name, _NOTSET)
        self._undo.append(lambda: dic.__setitem__(name, old) if old is not _NOTSET else dic.pop(name, None))
        dic[name] = value

    def delitem(self, dic, name, raising=True):
        if name not in dic:
            if raising:
                raise KeyError(name)
            return
        old = dic[name]
        self._undo.append(lambda: dic.__setitem__(name, old))
        del dic[name]

    def setenv(self, name, value, prepend=None):
        value = str(value)
        if prepend and name in os.environ:
            value = value + prepend + os.environ[name]
        self.setitem(os.environ, name, value)

    def delenv(self, name, raising=True):
        self.delitem(os.environ, name, raising)

    def chdir(self, path):
        old = os.getcwd()
        self._undo.append(lambda: os.chdir(old))
        os.chdir(path)

    def syspath_prepend(self, path):
        old = list(sys.path)
        self._undo.append(lambda: sys.path.__setitem__(slice(None), old))
        sys.path.insert(0, str(path))

    def undo(self):
        while self._undo:
            self._undo.pop()()


def _tmp_path():
    path = pathlib.Path(tempfile.mkdtemp(prefix="pytest-"))
    yield path
    shutil.rmtree(path, ignore_errors=True)


def _monkeypatch():
    patch = MonkeyPatch()
    yield patch
    patch.undo()


# ---- collecting -----------------------------------------------------------------------------

NO_RECURSE = {"build", "dist", "node_modules", "venv", "__pycache__", "CVS", "_darcs", "{arch}"}


def _is_test_file(name):
    return name.endswith(".py") and (name.startswith("test_") or name.endswith("_test.py"))


def _test_files(folder):
    for entry in sorted(os.scandir(folder), key=lambda e: e.name):
        if entry.is_dir():
            if not entry.name.startswith(".") and entry.name not in NO_RECURSE and not entry.name.endswith(".egg"):
                yield from _test_files(entry.path)
        elif _is_test_file(entry.name):
            yield entry.path


def _relative(path):
    return os.path.relpath(path, os.getcwd())


def _import(path):
    """Imports a test file the way pytest's default "prepend" mode does."""
    folder = os.path.dirname(path)
    names = [os.path.splitext(os.path.basename(path))[0]]
    while os.path.isfile(os.path.join(folder, "__init__.py")):
        names.insert(0, os.path.basename(folder))
        folder = os.path.dirname(folder)
    if folder not in sys.path:
        sys.path.insert(0, folder)
    return importlib.import_module(".".join(names))


def _fixtures_of(namespace):
    found = {}
    for value in vars(namespace).values():
        info = getattr(value, "_pytestfixture", None)
        if info and callable(value):
            found[info["name"]] = value
    return found


class Item:
    """One test to run: a function, a method of a test class, or one case of `parametrize`."""

    def __init__(self, path, module, cls, func, params, case, marks, fixtures):
        self.path, self.module, self.cls, self.func = path, module, cls, func
        self.params, self.marks, self.fixtures = params, marks, fixtures
        self.name = func.__name__ + (f"[{case}]" if case is not None else "")
        self.nodeid = "::".join([_relative(path), *([cls.__name__] if cls else []), self.name])


def _case_id(value, argname, index):
    if isinstance(value, (str, int, float, bool, complex, type(None))):
        return str(value)
    return f"{argname}{index}"


def _cases(marks):
    """The cases of every `parametrize` mark: (values by name, id, marks)."""
    groups = []
    for m in marks:
        if m.name != "parametrize":
            continue
        argnames, argvalues = m.args[0], list(m.args[1])
        names = [n.strip() for n in argnames.split(",") if n.strip()] if isinstance(argnames, str) else list(argnames)
        ids = m.kwargs.get("ids")
        group = []
        for i, value in enumerate(argvalues):
            extra, given = (), None
            if isinstance(value, ParameterSet):
                extra, given = value.marks, value.id
                value = value.values if len(names) > 1 else value.values[0]
            values = dict(zip(names, value)) if len(names) > 1 else {names[0]: value}
            if given is None and ids is not None:
                given = ids(value) if callable(ids) else ids[i]
            case = given if given is not None else "-".join(_case_id(values[n], n, i) for n in names)
            group.append((values, str(case), extra))
        groups.append(group)
    for combo in itertools.product(*groups):
        values, cases, extra = {}, [], []
        for v, c, e in combo:
            values.update(v)
            cases.append(c)
            extra.extend(e)
        yield values, "-".join(cases) if groups else None, extra


def _collect(path, module, conftest_fixtures):
    items = []
    module_fixtures = {**conftest_fixtures, **_fixtures_of(module)}

    def add(func, cls):
        marks = [*getattr(module, "pytestmark", []), *(getattr(cls, "pytestmark", []) if cls else []), *getattr(func, "pytestmark", [])]
        fixtures = {**module_fixtures, **(_fixtures_of(cls) if cls else {})}
        for values, case, extra in _cases(marks):
            items.append(Item(path, module, cls, func, values, case, marks + list(extra), fixtures))

    for name, value in list(vars(module).items()):
        if name.startswith("test") and inspect.isfunction(value) and not hasattr(value, "_pytestfixture"):
            add(value, None)
        elif name.startswith("Test") and inspect.isclass(value) and value.__init__ is object.__init__:
            for attr in dir(value):
                method = getattr(value, attr)
                if attr.startswith("test") and inspect.isfunction(method) and not hasattr(method, "_pytestfixture"):
                    add(method, value)
    return items


# ---- running --------------------------------------------------------------------------------


class Report:
    def __init__(self, item, outcome, error=None, reason="", output=None, message=""):
        self.item, self.outcome, self.error, self.reason, self.output = item, outcome, error, reason, output
        self.message = message


def _mark(marks, name):
    return next((m for m in reversed(marks) if m.name == name), None)


def _skip_reason(marks):
    for m in marks:
        if m.name == "skip":
            return m.kwargs.get("reason", m.args[0] if m.args else "unconditional skip")
        if m.name == "skipif" and m.args and m.args[0]:
            return m.kwargs.get("reason", "condition: " + str(m.args[0]))
    return None


class _Session:
    def __init__(self, capture):
        self.capture = capture
        self.cache = {"session": {}, "module": {}}
        self.teardowns = {"session": [], "module": []}

    def finish(self, scope):
        errors = []
        while self.teardowns[scope]:
            try:
                self.teardowns[scope].pop()()
            except BaseException as e:
                errors.append(e)
        self.cache[scope].clear()
        return errors

    def run(self, item):
        reason = _skip_reason(item.marks)
        if reason is not None:
            return Report(item, "skipped", reason=reason)
        xfail_mark = _mark(item.marks, "xfail")
        if xfail_mark and xfail_mark.args and not xfail_mark.args[0]:
            xfail_mark = None
        capture = _Capture(self.capture)
        cache, teardowns = {}, []
        instance = item.cls() if item.cls else None
        builtin = {
            "tmp_path": _tmp_path,
            "capsys": lambda: CaptureFixture(capture),
            "monkeypatch": _monkeypatch,
            "request": lambda: _Request(item, teardowns),
        }

        def value(name, needed_by):
            if name in item.params:
                return item.params[name]
            fn = item.fixtures.get(name) or builtin.get(name)
            if fn is None:
                raise _FixtureMissing(f"fixture '{name}' not found")
            if item.cls and vars(item.cls).get(fn.__name__) is fn:
                fn = getattr(instance, fn.__name__)
            if name in needed_by:
                raise _FixtureMissing(f"recursive dependency involving fixture '{name}'")
            scope = getattr(fn, "_pytestfixture", {}).get("scope", "function")
            scope = "session" if scope in ("session", "package") else "module" if scope in ("module", "class") else "function"
            store = cache if scope == "function" else self.cache[scope]
            if name in store:
                return store[name]
            args = {p: value(p, needed_by + [name]) for p in _parameters(fn)}
            result = fn(**args)
            if inspect.isgenerator(result):
                generator = result
                result = next(generator)
                (teardowns if scope == "function" else self.teardowns[scope]).append(lambda: _finish(generator))
            store[name] = result
            return result

        error, message = None, ""
        func = item.func if instance is None else getattr(instance, item.func.__name__)
        wanted = _parameters(func)
        try:
            with capture:
                autouse = [n for n, f in item.fixtures.items() if f._pytestfixture.get("autouse")]
                kwargs = {}
                for name in autouse + wanted:
                    resolved = value(name, [])
                    if name in wanted:
                        kwargs[name] = resolved
                if inspect.iscoroutinefunction(func):
                    raise Skipped("async def functions are not natively supported")
                func(**kwargs)
        except Skipped as e:
            return Report(item, "skipped", reason=e.msg or "")
        except BaseException as e:
            error = e
            # Said now, while the values the assert compared are as they failed.
            with capture:
                message = _message(e)
        finally:
            with capture:
                while teardowns:
                    try:
                        teardowns.pop()()
                    except BaseException as e:
                        error = error or e
        output = capture.read()
        if xfail_mark:
            if error is not None:
                return Report(item, "xfailed", reason=xfail_mark.kwargs.get("reason", ""))
            return Report(item, "xpassed", reason=xfail_mark.kwargs.get("reason", ""))
        if isinstance(error, XFailed):
            return Report(item, "xfailed", reason=error.msg or "")
        if error is not None:
            message = message or _message(error)
            return Report(item, "error" if isinstance(error, _FixtureMissing) else "failed", error=error, output=output, message=message)
        return Report(item, "passed")


class _FixtureMissing(Exception):
    pass


class _Request:
    """The `request` fixture, in part: the test's name and `addfinalizer`."""

    def __init__(self, item, teardowns):
        self.node = item
        self.function = item.func
        self.cls = item.cls
        self.module = item.module
        self._teardowns = teardowns

    def addfinalizer(self, fn):
        self._teardowns.append(fn)


def _parameters(fn):
    params = list(inspect.signature(fn).parameters.values())
    return [p.name for p in params if p.default is inspect.Parameter.empty and p.kind in (p.POSITIONAL_OR_KEYWORD, p.KEYWORD_ONLY)]


def _finish(generator):
    try:
        next(generator)
    except StopIteration:
        return
    raise RuntimeError("fixture function has more than one 'yield'")


# ---- reporting ------------------------------------------------------------------------------


def _line(title="", fill="="):
    if not title:
        return fill * WIDTH
    title = f" {title} "
    if len(title) + 2 > WIDTH:
        return title.strip()
    left = (WIDTH - len(title)) // 2
    return fill * left + title + fill * (WIDTH - len(title) - left)


def _is_own(filename):
    return not filename.startswith(("/lib/", "<frozen")) and filename != __file__


def _frames(error):
    tb = error.__traceback__
    frames = []
    while tb is not None:
        if _is_own(tb.tb_frame.f_code.co_filename):
            frames.append((tb.tb_frame, tb.tb_lineno))
        tb = tb.tb_next
    return frames


def _source(frame, line):
    """The frame's function up to the line that failed, as pytest prints it."""
    try:
        lines, start = inspect.getsourcelines(frame.f_code)
    except (OSError, TypeError):
        import linecache

        text = linecache.getline(frame.f_code.co_filename, line)
        return [(">   " + text.rstrip("\n")) if text else ""], text
    if start == 0:
        start = 1
    shown = lines[: line - start + 1] if start <= line < start + len(lines) else lines
    out = ["    " + text.rstrip("\n") for text in shown[:-1]]
    failing = shown[-1].rstrip("\n") if shown else ""
    out.append(">   " + failing)
    return out, failing


def _message(error):
    why = explain(error) if isinstance(error, AssertionError) else None
    if why:
        return why
    if isinstance(error, OutcomeException):
        return f"{type(error).__name__}: {error.msg or ''}".rstrip(": ")
    text = str(error)
    return f"{type(error).__name__}: {text}" if text else type(error).__name__


def _failure(report):
    error = report.error
    lines = [_line(report.item.name if not report.item.cls else f"{report.item.cls.__name__}.{report.item.name}", "_"), ""]
    frames = _frames(error)
    if isinstance(error, _FixtureMissing):
        lines.append(f"file {_relative(report.item.path)}, test {report.item.name}")
        lines.append(f"E       {error}")
        return lines
    for i, (frame, line) in enumerate(frames):
        source, failing = _source(frame, line)
        lines.extend(source)
        place = f"{_relative(frame.f_code.co_filename)}:{line}"
        if i == len(frames) - 1:
            indent = " " * (len(failing) - len(failing.lstrip()))
            for text in report.message.split("\n"):
                lines.append(f"E   {indent}{text}")
            lines.append("")
            lines.append(f"{place}: {type(error).__name__}")
        else:
            lines.append("")
            lines.append(f"{place}: in {frame.f_code.co_name}")
            lines.append(" ".join("_" * (WIDTH // 2)))
    if not frames:
        lines.append(f"E   {report.message}")
    out, err = report.output or ("", "")
    if out:
        lines += [_line("Captured stdout call", "-"), out.rstrip("\n")]
    if err:
        lines += [_line("Captured stderr call", "-"), err.rstrip("\n")]
    return lines


def _collection_error(path, error):
    """Why a test file could not be imported: its own frames, then the error."""
    lines = []
    if isinstance(error, ImportError):
        lines.append(f"ImportError while importing test module '{_relative(path)}'.")
    lines.append("Traceback:")
    for frame, line in _frames(error):
        if frame.f_code.co_filename.startswith("<"):
            continue
        import linecache

        lines.append(f"{_relative(frame.f_code.co_filename)}:{line}: in {frame.f_code.co_name}")
        source = linecache.getline(frame.f_code.co_filename, line).strip()
        if source:
            lines.append(f"    {source}")
    for text in "".join(traceback.format_exception_only(error)).rstrip("\n").split("\n"):
        lines.append(f"E   {text}")
    return lines


def _summary(counts, seconds):
    order = ["failed", "passed", "skipped", "xfailed", "xpassed", "error"]
    parts = []
    for name in order:
        n = counts.get(name, 0)
        if n:
            parts.append(f"{n} {'errors' if name == 'error' and n > 1 else name}")
    text = ", ".join(parts) or "no tests ran"
    return f"{text} in {seconds:.2f}s"


SYMBOL = {"passed": ".", "failed": "F", "skipped": "s", "xfailed": "x", "xpassed": "X", "error": "E"}
WORD = {"passed": "PASSED", "failed": "FAILED", "skipped": "SKIPPED", "xfailed": "XFAIL", "xpassed": "XPASS", "error": "ERROR"}


def _keyword(expression):
    """`-k`: words matched against test names, with `and`, `or`, `not` and parentheses."""
    tokens = re.findall(r"\(|\)|[^\s()]+", expression)
    code = []
    for token in tokens:
        if token in ("and", "or", "not", "(", ")"):
            code.append(token)
        else:
            code.append(f"({token.lower()!r} in name)")
    source = " ".join(code)
    return lambda name: eval(source, {}, {"name": name.lower()})


def main(args=None):
    """Runs the tests and prints the report. Returns the exit code: 0 when every test passed."""
    args = list(sys.argv[1:] if args is None else args)
    started = time.perf_counter()
    quiet = verbose = exitfirst = False
    capture = True
    keyword = None
    targets = []
    i = 0
    while i < len(args):
        arg = args[i]
        if arg in ("-q", "--quiet"):
            quiet = True
        elif arg in ("-v", "--verbose", "-vv"):
            verbose = True
        elif arg in ("-x", "--exitfirst"):
            exitfirst = True
        elif arg in ("-s", "--capture=no"):
            capture = False
        elif arg == "-k" and i + 1 < len(args):
            i += 1
            keyword = _keyword(args[i])
        elif arg.startswith("-k") and len(arg) > 2:
            keyword = _keyword(arg[2:])
        elif not arg.startswith("-"):
            targets.append(arg)
        i += 1

    root = os.getcwd()
    paths, selections = [], {}
    for target in targets or ["."]:
        path, _, name = target.partition("::")
        full = os.path.abspath(path)
        if os.path.isdir(full):
            paths.extend(_test_files(full))
        elif os.path.isfile(full):
            paths.append(full)
            if name:
                selections.setdefault(full, []).append(name)
        else:
            print(f"ERROR: file or directory not found: {target}")
            print()
            print(_line(f"no tests ran in {time.perf_counter() - started:.2f}s") if not quiet else f"no tests ran in {time.perf_counter() - started:.2f}s")
            return 4

    items, errors = [], []
    loaded_conftests = {}
    for path in paths:
        conftest_fixtures = {}
        folder = root
        chain = [root]
        for part in os.path.relpath(os.path.dirname(path), root).split(os.sep):
            if part and part != ".":
                folder = os.path.join(folder, part)
                chain.append(folder)
        try:
            with _Capture(True):
                for folder in chain:
                    conftest = os.path.join(folder, "conftest.py")
                    if os.path.isfile(conftest):
                        if conftest not in loaded_conftests:
                            name = "conftest_" + str(len(loaded_conftests))
                            spec = importlib.util.spec_from_file_location(name, conftest)
                            module = importlib.util.module_from_spec(spec)
                            sys.modules[name] = module
                            spec.loader.exec_module(module)
                            loaded_conftests[conftest] = _fixtures_of(module)
                        conftest_fixtures.update(loaded_conftests[conftest])
                module = _import(path)
        except BaseException as e:
            if isinstance(e, Skipped):
                continue
            errors.append((path, e))
            continue
        found = _collect(path, module, conftest_fixtures)
        if path in selections:
            found = [it for it in found if it.name in selections[path] or it.func.__name__ in selections[path] or (it.cls and it.cls.__name__ in selections[path])]
        if keyword:
            found = [it for it in found if keyword(it.nodeid)]
        items.extend(found)

    if not quiet:
        print(_line("test session starts"))
        print(f"collected {len(items)} item{'' if len(items) == 1 else 's'}" + (f" / {len(errors)} error{'' if len(errors) == 1 else 's'}" if errors else ""))
        print()

    if errors:
        print(_line("ERRORS"))
        for path, e in errors:
            print(_line(f"ERROR collecting {_relative(path)}", "_"))
            for text in _collection_error(path, e):
                print(text)
        print(_line("short test summary info"))
        for path, _ in errors:
            print(f"ERROR {_relative(path)}")
        print(_line(f"Interrupted: {len(errors)} error{'' if len(errors) == 1 else 's'} during collection", "!"))
        seconds = time.perf_counter() - started
        text = f"{len(errors)} error{'' if len(errors) == 1 else 's'} in {seconds:.2f}s"
        print(text if quiet else _line(text))
        return 2

    session = _Session(capture)
    reports = []
    current = None
    progress = ""
    stop = False
    for index, item in enumerate(items):
        if item.path != current:
            if current is not None:
                session.finish("module")
                if not verbose:
                    _progress(progress, current, quiet, index, len(items))
            current, progress = item.path, ""
        report = session.run(item)
        reports.append(report)
        if verbose:
            percent = f"[{round(100 * (index + 1) / len(items)):3d}%]"
            print(f"{item.nodeid} {WORD[report.outcome]} {percent}")
        else:
            progress += SYMBOL[report.outcome]
        if exitfirst and report.outcome in ("failed", "error"):
            stop = True
            break
    if current is not None:
        session.finish("module")
        if not verbose:
            _progress(progress, current, quiet, len(reports), len(items))
    session.finish("session")

    failed = [r for r in reports if r.outcome in ("failed", "error")]
    if failed:
        print()
        print(_line("FAILURES"))
        for report in failed:
            for text in _failure(report):
                print(text)
    if failed or any(r.outcome in ("skipped", "xfailed", "xpassed") for r in reports):
        lines = []
        for r in reports:
            if r.outcome in ("failed", "error"):
                first = r.message.split("\n")[0]
                lines.append(f"{WORD[r.outcome]} {r.item.nodeid} - {first}")
        if lines:
            print(_line("short test summary info"))
            for text in lines:
                print(text)
    if stop:
        print(_line("stopping after 1 failures", "!"))
    counts = {}
    for r in reports:
        counts[r.outcome] = counts.get(r.outcome, 0) + 1
    text = _summary(counts, time.perf_counter() - started)
    print(text if quiet else _line(text))
    if not items:
        return 5
    return 1 if failed else 0


def _progress(progress, path, quiet, done, total):
    percent = f"[{round(100 * done / total):3d}%]"
    text = progress if quiet else f"{_relative(path)} {progress}"
    gap = WIDTH - len(text) - len(percent)
    print(text + (" " * gap if gap > 0 else " ") + percent)


def console_main():
    raise SystemExit(main())


if __name__ == "__main__":
    console_main()

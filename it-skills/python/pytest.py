"""
A small pytest for the app's Python.

The parts of pytest a learner meets: test discovery (`test_*.py` files, `test*` functions and
methods of `Test*` classes), a failed `assert` reported with the values it compared,
`pytest.raises`, `approx`, `fail` and `skip`, fixtures (with `yield`, `params` and `request.param`,
`conftest.py`, and the built-in `tmp_path`, `capsys` and `monkeypatch`), `mark.parametrize`, `skip`,
`skipif` and `xfail`, and the options -q, -v, -x, -s, -k and -m. The same tests pass and fail as
under pytest, and the report reads the same, only narrower: a phone's terminal is about forty
characters wide. There are no plugins or configuration files, so an `async def` test fails, as
pytest 8.4 and later fail it without a plugin.
"""

import builtins
import collections
import contextlib
import enum
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

    def __init__(self, msg=None, pytrace=True):
        super().__init__(msg)
        self.msg = msg
        # False: the report shows the message alone, without the test's code.
        self.pytrace = pytrace

    def __str__(self):
        return self.msg or ""


class Failed(OutcomeException):
    pass


class Skipped(OutcomeException):
    pass


class XFailed(Failed):
    pass


def fail(reason="", pytrace=True):
    raise Failed(reason, pytrace)


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
    """
    `@pytest.fixture`: what a test receives by naming it as a parameter. With `params`, every
    test that uses it runs once for each, and the fixture reads the current one as `request.param`.
    """

    def register(fn):
        fn._pytestfixture = {"scope": scope, "autouse": autouse, "name": name or fn.__name__, "params": None if params is None else list(params), "ids": ids}
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
        # The mark `fixture` left, read without asking the object: a Mock makes up any attribute it is asked for.
        info = inspect.getattr_static(value, "_pytestfixture", None)
        if isinstance(info, dict) and callable(value):
            found[info["name"]] = value
    return found


class Item:
    """
    One test to run: a function, a method of a test class, or one case of its parameters —
    `params` by name from `parametrize`, `fixture_params` by fixture name: (value, index, scope).
    """

    def __init__(self, path, module, cls, func, params, case, marks, fixtures, fixture_params=None):
        self.path, self.module, self.cls, self.func = path, module, cls, func
        self.params, self.marks, self.fixtures = params, marks, fixtures
        self.fixture_params = fixture_params or {}
        self.name = func.__name__ + (f"[{case}]" if case is not None else "")
        self.nodeid = "::".join([_relative(path), *([cls.__name__] if cls else []), self.name])


# ---- test ids, as pytest makes them ---------------------------------------------------------

_NON_PRINTABLE = {i: f"\\x{i:02x}" for i in range(128) if i not in range(32, 127)}
_NON_PRINTABLE.update({ord("\t"): "\\t", ord("\r"): "\\r", ord("\n"): "\\n"})


def _escaped(value):
    """Text in a test id: what is not printable ASCII is written as its escape, `\\u043e`."""
    if isinstance(value, bytes):
        text = value.decode("ascii", "backslashreplace")
    else:
        text = str(value).encode("unicode_escape").decode("ascii")
    return text.translate(_NON_PRINTABLE)


def _value_id(value):
    if isinstance(value, (str, bytes)):
        return _escaped(value)
    if value is None or isinstance(value, (float, int, bool, complex)):
        return str(value)
    if isinstance(value, re.Pattern):
        return _escaped(value.pattern)
    if isinstance(value, enum.Enum):
        return str(value)
    name = getattr(value, "__name__", None)
    # A class or a function: its name.
    return name if isinstance(name, str) else None


def _one_id(value, argname, index, idfn):
    if idfn is not None:
        given = idfn(value)
        if given is not None and _value_id(given) is not None:
            return _value_id(given)
    found = _value_id(value)
    return found if found is not None else f"{argname}{index}"


def _ids(argnames, sets, ids):
    """
    The id of each parameter set: its own (`pytest.param(id=)`), the one `ids` gives, or one
    made from its values (`argname` + index for a value without one); an id that repeats is numbered.
    """
    idfn = ids if callable(ids) else None
    listed = None if callable(ids) else ids
    found = []
    for index, one in enumerate(sets):
        if one.id is not None:
            found.append(_escaped(one.id))
        elif listed is not None and index < len(listed) and listed[index] is not None:
            given = listed[index]
            found.append(_value_id(given) if _value_id(given) is not None else str(given))
        else:
            found.append("-".join(_one_id(v, n, index, idfn) for v, n in zip(one.values, argnames)))
    counts = collections.Counter(found)
    if len(counts) < len(found):
        suffixes = collections.defaultdict(int)
        taken = set(found)
        for index, one in enumerate(found):
            if counts[one] > 1:
                sep = "_" if one and one[-1].isdigit() else ""
                new = f"{one}{sep}{suffixes[one]}"
                while new in taken:
                    suffixes[one] += 1
                    new = f"{one}{sep}{suffixes[one]}"
                found[index] = new
                suffixes[one] += 1
    return found


def _sets(argnames, argvalues):
    """`parametrize` values as parameter sets: a `pytest.param` as it is, a bare value as one."""
    sets = []
    for value in argvalues:
        if isinstance(value, ParameterSet):
            sets.append(value)
        else:
            sets.append(ParameterSet(tuple(value) if len(argnames) > 1 else (value,), (), None))
    return sets


# ---- scopes ---------------------------------------------------------------------------------

_SCOPE_RANK = {"function": 0, "class": 1, "module": 2, "package": 3, "session": 4}


def _scope_of(fn):
    return getattr(fn, "_pytestfixture", {}).get("scope", "function")


def _kept_in(scope):
    """Where a fixture of `scope` is kept: the app keeps a class's fixtures with the module's."""
    return "session" if scope in ("session", "package") else "module" if scope in ("module", "class") else "function"


def _closure(func, fixtures, direct):
    """
    The fixtures a test uses, in pytest's order: the autouse ones and its own arguments, then
    what those use, higher scopes first. A name `parametrize` gives directly is no fixture.
    """
    names = list(dict.fromkeys([n for n, f in fixtures.items() if f._pytestfixture.get("autouse")] + _parameters(func)))
    i = 0
    while i < len(names):
        fn = fixtures.get(names[i])
        if fn is not None and names[i] not in direct:
            for name in _parameters(fn):
                if name not in names:
                    names.append(name)
        i += 1
    return sorted(names, key=lambda n: _SCOPE_RANK.get(_scope_of(fixtures[n]), 0) if n in fixtures and n not in direct else 0, reverse=True)


def _cases(func, nearest, fixtures):
    """
    The cases of a test: (values by name, id, marks, fixture params). Each fixture with
    `params` it uses is one axis, then each `parametrize` mark, nearest first (`nearest`: the
    function's marks, its class's, its module's); the first axis is the outer loop, and the
    case's id joins the axes' ids in that order.
    """
    parametrize = [m for m in nearest if m.name == "parametrize"]
    groups, marked, direct = [], set(), set()
    for m in parametrize:
        argnames = m.args[0]
        names = [n.strip() for n in argnames.split(",") if n.strip()] if isinstance(argnames, str) else list(argnames)
        # `indirect`: the values go to the fixtures of those names, as their `request.param`.
        indirect = m.kwargs.get("indirect", False)
        through = set(names) if indirect is True else set(indirect or ())
        marked.update(names)
        direct.update(n for n in names if n not in through)
        sets = _sets(names, list(m.args[1]))
        ids = _ids(names, sets, m.kwargs.get("ids"))
        group = []
        for index, (one, case) in enumerate(zip(sets, ids)):
            values = dict(zip(names, one.values))
            given = {n: (v, index, _kept_in(_scope_of(fixtures.get(n)))) for n, v in values.items() if n in through}
            group.append(({n: v for n, v in values.items() if n not in through}, case, one.marks, given))
        groups.append(group)
    axes = []
    for name in _closure(func, fixtures, direct):
        fn = fixtures.get(name)
        info = getattr(fn, "_pytestfixture", None) if name not in marked else None
        if not info or info.get("params") is None:
            continue
        sets = _sets([name], info["params"])
        ids = _ids([name], sets, info.get("ids"))
        scope = _kept_in(info.get("scope", "function"))
        axes.append([({}, case, one.marks, {name: (one.values[0], index, scope)}) for index, (one, case) in enumerate(zip(sets, ids))])
    groups = axes + groups
    for combo in itertools.product(*groups):
        values, cases, extra, fixture_params = {}, [], [], {}
        for v, c, e, f in combo:
            values.update(v)
            cases.append(c)
            extra.extend(e)
            fixture_params.update(f)
        yield values, "-".join(cases) if groups else None, extra, fixture_params


def _collect(path, module, conftest_fixtures):
    items = []
    module_fixtures = {**conftest_fixtures, **_fixtures_of(module)}

    def add(func, cls):
        own = [getattr(module, "pytestmark", []), getattr(cls, "pytestmark", []) if cls else [], getattr(func, "pytestmark", [])]
        marks = [m for level in own for m in level]
        fixtures = {**module_fixtures, **(_fixtures_of(cls) if cls else {})}
        for values, case, extra, fixture_params in _cases(func, [m for level in reversed(own) for m in level], fixtures):
            items.append(Item(path, module, cls, func, values, case, marks + list(extra), fixtures, fixture_params))

    for name, value in list(vars(module).items()):
        if name.startswith("test") and inspect.isfunction(value) and not hasattr(value, "_pytestfixture"):
            add(value, None)
        elif name.startswith("Test") and inspect.isclass(value) and value.__init__ is object.__init__:
            for attr in dir(value):
                method = getattr(value, attr)
                if attr.startswith("test") and inspect.isfunction(method) and not hasattr(method, "_pytestfixture"):
                    add(method, value)
    return items


def _reorder(items):
    """
    As pytest orders the tests that use a module or session fixture with `params`: those of
    one param together, so that each is set up once (pytest's reorder_items).
    """
    scopes = ["session", "module"]
    keys_by_item = {scope: {} for scope in scopes}
    items_by_key = {scope: collections.defaultdict(dict) for scope in scopes}
    for scope in scopes:
        for item in items:
            keys = {(name, index, None if scope == "session" else item.path): None for name, (_, index, kept) in item.fixture_params.items() if kept == scope}
            if keys:
                keys_by_item[scope][item] = keys
                for key in keys:
                    items_by_key[scope][key][item] = None

    def at(items, level):
        if level == len(scopes) or len(items) < 3:
            return items
        scope = scopes[level]
        ignore = set()
        queue = collections.deque(items)
        done = {}
        while queue:
            plain = {}
            slicing = None
            while queue:
                item = queue.popleft()
                if item in done or item in plain:
                    continue
                keys = dict.fromkeys(k for k in keys_by_item[scope].get(item, ()) if k not in ignore)
                if not keys:
                    plain[item] = None
                else:
                    slicing, _ = keys.popitem()
                    matching = [i for i in items_by_key[scope][slicing] if i in items]
                    for i in reversed(matching):
                        queue.appendleft(i)
                        for other in scopes:
                            for key in keys_by_item[other].get(i, ()):
                                order = items_by_key[other][key]
                                order.pop(i, None)
                                items_by_key[other][key] = {i: None, **order}
                    break
            if plain:
                done.update(at(plain, level + 1))
            if slicing is not None:
                ignore.add(slicing)
        return done

    return list(at(dict.fromkeys(items), 0))


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


_ASYNC = (
    "async def functions are not natively supported.\n"
    "You need to install a suitable plugin for your async framework, for example:\n"
    "  - anyio\n"
    "  - pytest-asyncio\n"
    "  - pytest-tornasync\n"
    "  - pytest-trio\n"
    "  - pytest-twisted"
)


class _Session:
    """
    Runs the tests one by one with their fixtures. A module or session fixture is kept for
    the tests after: `cache[scope]` holds it by name with the index of its param, and
    `teardowns[scope]` its teardowns, in the order they were set up, by name.
    """

    def __init__(self, capture):
        self.capture = capture
        self.cache = {"session": {}, "module": {}}
        self.teardowns = {"session": [], "module": []}

    def finish(self, scope):
        errors = []
        while self.teardowns[scope]:
            try:
                self.teardowns[scope].pop()[1]()
            except BaseException as e:
                errors.append(e)
        self.cache[scope].clear()
        return errors

    def _drop(self, scope, name):
        """Another param of `name` is wanted: it is torn down, with what was set up after it."""
        kept = self.teardowns[scope]
        while name in self.cache[scope]:
            if not kept:
                self.cache[scope].pop(name)
                break
            owner, teardown = kept.pop()
            try:
                teardown()
            finally:
                self.cache[scope].pop(owner, None)

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
        }

        def request_for(fixture):
            """The `request` a test (`fixture` None) or one of its fixtures receives."""
            if fixture is None:
                return TopRequest(item, lambda fn: teardowns.append((None, fn)))
            fn = item.fixtures.get(fixture)
            scope = _kept_in(_scope_of(fn))
            kept = teardowns if scope == "function" else self.teardowns[scope]
            return SubRequest(item, fixture, _scope_of(fn), item.fixture_params.get(fixture), lambda finalizer: kept.append((fixture, finalizer)))

        def value(name, needed_by):
            if name in item.params:
                return item.params[name]
            if name == "request":
                return request_for(needed_by[-1] if needed_by else None)
            fn = item.fixtures.get(name) or builtin.get(name)
            if fn is None:
                raise _FixtureMissing(f"fixture '{name}' not found")
            if item.cls and vars(item.cls).get(fn.__name__) is fn:
                fn = getattr(instance, fn.__name__)
            if name in needed_by:
                raise _FixtureMissing(f"recursive dependency involving fixture '{name}'")
            scope = _kept_in(_scope_of(fn))
            param = item.fixture_params.get(name)
            index = param[1] if param else None
            if scope == "function":
                if name in cache:
                    return cache[name]
            elif name in self.cache[scope]:
                if self.cache[scope][name][0] == index:
                    return self.cache[scope][name][1]
                self._drop(scope, name)
            args = {p: value(p, needed_by + [name]) for p in _parameters(fn)}
            result = fn(**args)
            if inspect.isgenerator(result):
                generator = result
                result = next(generator)
                (teardowns if scope == "function" else self.teardowns[scope]).append((name, lambda: _finish(generator)))
            if scope == "function":
                cache[name] = result
            else:
                self.cache[scope][name] = (index, result)
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
                # As pytest 8.4 and later: with no plugin to run it, an async test fails.
                if inspect.iscoroutinefunction(func) or inspect.isasyncgenfunction(func):
                    fail(_ASYNC, pytrace=False)
                result = func(**kwargs)
                if hasattr(result, "__await__") or hasattr(result, "__aiter__"):
                    with contextlib.suppress(Exception):
                        result.close()
                    fail(_ASYNC, pytrace=False)
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
                        teardowns.pop()[1]()
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


class TopRequest:
    """The `request` a test receives: its test, and `addfinalizer`."""

    scope = "function"
    fixturename = None

    def __init__(self, item, finalize):
        self.node = item
        self.function = item.func
        self.cls = item.cls
        self.module = item.module
        self._finalize = finalize

    def addfinalizer(self, fn):
        self._finalize(fn)

    def __repr__(self):
        return f"<FixtureRequest for <Function {self.node.name}>>"


class SubRequest(TopRequest):
    """
    The `request` a fixture receives: also its name and scope, and with `params` the one this
    test runs with, `request.param` (only then: `request.param` of another fails, as in pytest).
    """

    def __init__(self, item, fixturename, scope, param, finalize):
        super().__init__(item, finalize)
        self.fixturename, self.scope = fixturename, scope
        self.param_index = 0
        if param is not None:
            self.param, self.param_index = param[0], param[1]

    def __repr__(self):
        return f"<SubRequest {self.fixturename!r} for <Function {self.node.name}>>"


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
    if isinstance(error, OutcomeException) and not error.pytrace:
        # `fail(..., pytrace=False)`: the message alone, as it was written.
        lines[1:] = str(error.msg or "").split("\n")
        frames = []
    elif isinstance(error, _FixtureMissing):
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
    if not frames and getattr(error, "pytrace", True):
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
    order = ["failed", "passed", "skipped", "deselected", "xfailed", "xpassed", "error"]
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


def _markers(expression):
    """`-m`: names of marks a test must have (its own, its class's, its module's), with `and`, `or`, `not` and parentheses."""
    tokens = re.findall(r"\(|\)|[^\s()]+", expression)
    source = " ".join(token if token in ("and", "or", "not", "(", ")") else f"({token!r} in names)" for token in tokens)
    return lambda item: eval(source, {}, {"names": {m.name for m in item.marks}})


def main(args=None):
    """Runs the tests and prints the report. Returns the exit code: 0 when every test passed."""
    args = list(sys.argv[1:] if args is None else args)
    started = time.perf_counter()
    quiet = verbose = exitfirst = False
    capture = True
    keyword = marker = None
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
        elif arg == "-m" and i + 1 < len(args):
            i += 1
            marker = _markers(args[i])
        elif arg.startswith("-m") and len(arg) > 2:
            marker = _markers(arg[2:])
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
    deselected = 0
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
        chosen = [it for it in found if (not keyword or keyword(it.nodeid)) and (not marker or marker(it))]
        deselected += len(found) - len(chosen)
        items.extend(chosen)

    collected = len(items) + deselected
    if not quiet:
        print(_line("test session starts"))
        print(
            f"collected {collected} item{'' if collected == 1 else 's'}"
            + (f" / {len(errors)} error{'' if len(errors) == 1 else 's'}" if errors else "")
            + (f" / {deselected} deselected / {len(items)} selected" if deselected else "")
        )
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

    items = _reorder(items)
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

    # As pytest: a blank line after the tests' progress, unless -q.
    if reports and not quiet:
        print()
    failed = [r for r in reports if r.outcome in ("failed", "error")]
    if failed:
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
    counts = {"deselected": deselected}
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

"""
How the app runs a learner's program: the Python half of runner.js.

A program runs as `__main__` in a folder holding only its own files, the way `python main.py`
runs it, and a run leaves nothing behind for the next one. What it prints and how it fails are
what a terminal shows. The module is installed in site-packages, under /lib, so its frames stay
out of a learner's traceback, like Pyodide's own.
"""

import ast
import asyncio
import builtins
import concurrent.futures
import contextlib
import concurrent.futures.thread
import gc
import importlib
import importlib.util
import io
import itertools
import linecache
import logging
import os
import shutil
import sys
import textwrap
import threading
import traceback
import warnings

from pyodide.webloop import PyodideTask, WebLoop

# The folder a program runs in: the terminal's.
APP = "/app"
# A check's code, as a traceback names it.
CHECK = "check.py"
os.makedirs(APP, exist_ok=True)
os.chdir(APP)

# Python's own folders. A program's folder goes in front of them, as `python main.py` puts it.
_SYS_PATH = [p for p in sys.path if p not in ("", APP)]
# No __pycache__ folders among a learner's files.
sys.dont_write_bytecode = True


# A browser gives Python one thread, and no processes. An executor here runs each task as it is
# submitted, and a thread runs its work when it starts: results, their order and their errors are
# what real threads and processes give; only the time they take is not.


class _InlineExecutor(concurrent.futures.Executor):
    def __init__(self, max_workers=None, *args, **kwargs):
        if max_workers is not None and max_workers <= 0:
            raise ValueError("max_workers must be greater than 0")
        self._max_workers = max_workers
        self._shutdown = False

    def submit(self, fn, /, *args, **kwargs):
        if self._shutdown:
            raise RuntimeError("cannot schedule new futures after shutdown")
        future = concurrent.futures.Future()
        future.set_running_or_notify_cancel()
        try:
            future.set_result(fn(*args, **kwargs))
        except BaseException as e:
            future.set_exception(e)
        return future

    def shutdown(self, wait=True, *, cancel_futures=False):
        self._shutdown = True


class ThreadPoolExecutor(_InlineExecutor):
    pass


class ProcessPoolExecutor(_InlineExecutor):
    pass


ThreadPoolExecutor.__module__ = ProcessPoolExecutor.__module__ = "concurrent.futures"
concurrent.futures.ThreadPoolExecutor = concurrent.futures.thread.ThreadPoolExecutor = ThreadPoolExecutor
concurrent.futures.ProcessPoolExecutor = ProcessPoolExecutor


def _start(self):
    if not self._initialized:
        raise RuntimeError("thread.__init__() not called")
    if self._started.is_set():
        raise RuntimeError("threads can only be started once")
    self._started.set()
    # While its work runs, the thread is the current one: current_thread().name says so.
    ident = threading.get_ident()
    caller = threading._active.get(ident)
    threading._active[ident] = self
    try:
        self.run()
    except BaseException:
        self._invoke_excepthook(self)
    finally:
        self._is_stopped = True
        if caller is None:
            del threading._active[ident]
        else:
            threading._active[ident] = caller


threading.Thread.start = _start


def _asyncio_run(main, *, debug=None, loop_factory=None):
    # A program runs inside the browser's event loop, which nothing can block on: runner.js
    # turns `asyncio.run()` outside functions into `await __ar()`. Inside a function, Python's
    # own message for a call from a running loop.
    if asyncio.iscoroutine(main):
        main.close()
    raise RuntimeError("asyncio.run() cannot be called from a running event loop")


asyncio.run = _asyncio_run

# An error the event loop cannot hand to anyone (a task's exception never retrieved, one at the
# end of an asyncio.run()) is told as Python's own event loop tells it, through the `asyncio`
# logger, and when Python tells it: a task's, once the task is gone and nobody asked for it —
# Pyodide's own loop tells it as soon as such a task fails.
WebLoop.default_exception_handler = asyncio.BaseEventLoop.default_exception_handler


def _decrement_in_progress(self, fut=None):
    self._in_progress -= 1
    if self._no_in_progress_handler and self._in_progress == 0:
        self._no_in_progress_handler()


WebLoop._decrement_in_progress = _decrement_in_progress
# A task is a Task, as Python names it in what it prints of one, and a program's tasks are
# numbered from Task-1, as in a new `python` (a run starts the count again).
PyodideTask.__name__ = PyodideTask.__qualname__ = "Task"
_TASK_NUMBERS = [itertools.count(1)]
_CREATE_TASK = WebLoop.create_task


def _create_task(self, coro, *, name=None, context=None):
    return _CREATE_TASK(self, coro, name=f"Task-{next(_TASK_NUMBERS[0])}" if name is None else name, context=context)


WebLoop.create_task = _create_task


async def _asyncio_main(main, *, debug=None, loop_factory=None):
    """
    `asyncio.run(main())` outside a function, as runner.js rewrites it: main() runs as the task
    asyncio.run makes of it, so `asyncio.timeout()`, `wait_for()` and `current_task()` work as
    they do there; when it ends, the tasks it left running are cancelled and the loop's
    exception handler and task factory are what they were, as a new loop's would be. A
    SystemExit or KeyboardInterrupt in any of its tasks ends it, as it stops Python's loop.
    """
    if not asyncio.iscoroutine(main):
        raise ValueError("a coroutine was expected, got {!r}".format(main))
    loop = asyncio.get_running_loop()
    before = asyncio.all_tasks()
    handler, factory = loop.get_exception_handler(), loop.get_task_factory()
    hooks = loop._system_exit_handler, loop._keyboard_interrupt_handler
    task = loop.create_task(main)
    stopped = []

    def stop(error):
        stopped.append(error)
        task.cancel()

    # A task's SystemExit leaves its step for the event loop, which hands it to these.
    loop._system_exit_handler = lambda code: stop(SystemExit(code))
    loop._keyboard_interrupt_handler = lambda: stop(KeyboardInterrupt())
    try:
        try:
            return await task
        except asyncio.CancelledError:
            if not stopped:
                raise
        raise stopped[0]
    finally:
        loop._system_exit_handler, loop._keyboard_interrupt_handler = hooks
        await _end_tasks(before)
        loop.set_exception_handler(handler)
        loop.set_task_factory(factory)
        # Python's asyncio.run ends with two tasks of its own (async generators, the executor).
        next(_TASK_NUMBERS[0])
        next(_TASK_NUMBERS[0])


builtins.__ar = _asyncio_main


# What a program may change for the whole interpreter, as it was before the first one: a run
# puts it back when it ends, as a new `python` would start with it.
_ENVIRON = dict(os.environ)
_STREAMS = (sys.stdin, sys.stdout, sys.stderr)
_RECURSION_LIMIT = sys.getrecursionlimit()
_INT_DIGITS = sys.get_int_max_str_digits()
_THREAD_HOOK = threading.excepthook
_WARNING_FILTERS = list(warnings.filters)
_SHOW_WARNING = warnings.showwarning
_LEVEL_NAMES = (dict(logging._levelToName), dict(logging._nameToLevel))
# Each logger made outside a program, by Python or by a package, as it was made. One that a
# program made goes back to what `getLogger` gives: no handlers and no level of its own.
_LOGGERS = {}
_NEW_LOGGER = (logging.NOTSET, (), (), True, False)


def _loggers():
    yield "", logging.root
    for name, logger in list(logging.Logger.manager.loggerDict.items()):
        if isinstance(logger, logging.Logger):
            yield name, logger


def _note_loggers():
    for name, logger in _loggers():
        if name not in _LOGGERS:
            _LOGGERS[name] = (logger.level, tuple(logger.handlers), tuple(logger.filters), logger.propagate, logger.disabled)


def _restore_logging():
    """Logging as it was: `basicConfig` in the next program configures it again."""
    for name, logger in _loggers():
        level, handlers, filters, propagate, disabled = _LOGGERS.get(name, _NEW_LOGGER)
        for handler in logger.handlers:
            if handler not in handlers:
                # A file handler writes what it holds into its file before the run hands it back.
                with contextlib.suppress(Exception):
                    handler.flush()
                    handler.close()
        logger.handlers[:] = handlers
        logger.filters[:] = filters
        logger.level, logger.propagate, logger.disabled = level, propagate, disabled
    logging.Logger.manager._clear_cache()
    logging.disable(logging.NOTSET)
    logging.captureWarnings(False)
    logging.setLoggerClass(logging.Logger)
    logging.setLogRecordFactory(logging.LogRecord)
    logging.raiseExceptions = True
    for table, saved in zip((logging._levelToName, logging._nameToLevel), _LEVEL_NAMES):
        table.clear()
        table.update(saved)


def _restore():
    _restore_logging()
    warnings.filters[:] = _WARNING_FILTERS
    warnings._filters_mutated()
    warnings.showwarning = _SHOW_WARNING
    if dict(os.environ) != _ENVIRON:
        os.environ.clear()
        os.environ.update(_ENVIRON)
    sys.setrecursionlimit(_RECURSION_LIMIT)
    sys.set_int_max_str_digits(_INT_DIGITS)
    threading.excepthook = _THREAD_HOOK


_note_loggers()


async def _end_tasks(before):
    """
    As `asyncio.run()` ends: the tasks a program left running are cancelled, and finish; one
    that ended with another error instead is reported, as asyncio.run reports it.
    """
    left = [task for task in asyncio.all_tasks() if task not in before]
    for task in left:
        task.cancel()
    if not left:
        return
    await asyncio.gather(*left, return_exceptions=True)
    loop = asyncio.get_running_loop()
    for task in left:
        if not task.cancelled() and task.exception() is not None:
            loop.call_exception_handler({"message": "unhandled exception during asyncio.run() shutdown", "exception": task.exception(), "task": task})


def _clear(folder):
    for name in os.listdir(folder):
        path = os.path.join(folder, name)
        if os.path.isdir(path) and not os.path.islink(path):
            shutil.rmtree(path)
        else:
            os.remove(path)


def _prepare(files, filename, cwd, module):
    """The program's folder with its files only, as if nothing had run before."""
    os.chdir(APP)
    _clear(APP)
    for name, text in files.items():
        path = os.path.join(APP, name.lstrip("/"))
        os.makedirs(os.path.dirname(path), exist_ok=True)
        with open(path, "w", encoding="utf-8") as f:
            f.write(text)
    # Modules the last run imported from its folder are imported anew, from what is there now.
    for name, module in list(sys.modules.items()):
        if (getattr(module, "__file__", None) or "").startswith(APP + "/"):
            del sys.modules[name]
    for path in list(sys.path_importer_cache):
        if path == APP or path.startswith(APP + "/"):
            del sys.path_importer_cache[path]
    folder = os.path.join(APP, cwd)
    if os.path.isdir(folder):
        os.chdir(folder)
    # `python -m` looks for the module from the folder it runs in, `python main.py` beside the file.
    sys.path[:] = [os.getcwd() if module else os.path.dirname(os.path.join(APP, filename))] + _SYS_PATH
    sys.argv[:] = [os.path.join(APP, filename) if module else filename]
    _note_loggers()


def _files():
    """The folder's text files after a run: what the program wrote is in a terminal's folder too."""
    found = {}
    for folder, dirs, names in os.walk(APP):
        dirs.sort()
        for name in sorted(names):
            path = os.path.join(folder, name)
            try:
                with open(path, encoding="utf-8") as f:
                    found[os.path.relpath(path, APP)] = f.read()
            except (UnicodeDecodeError, OSError):
                pass
    return found


def _exit_status(e):
    """sys.exit(): the status a shell sees. A message goes to stderr, as Python prints it."""
    if e.code is None:
        return 0
    if isinstance(e.code, int):
        return e.code
    print(e.code, file=sys.stderr)
    return 1


def shown(e):
    """
    The traceback as Python prints it, from the learner's first frame on. The frames of this
    module, which runs an `asyncio.run()` of the program's, are left out of every exception
    of it, chained or grouped.
    """
    te = traceback.TracebackException.from_exception(e)
    stack = list(te.stack)
    while stack and stack[0].filename.startswith(("/lib/", "<frozen ")):
        stack.pop(0)
    te.stack = stack
    seen, todo = set(), [te]
    while todo:
        one = todo.pop()
        if id(one) in seen:
            continue
        seen.add(id(one))
        one.stack = traceback.StackSummary.from_list([frame for frame in one.stack if frame.filename != __file__])
        todo.extend(other for other in (one.__cause__, one.__context__, *(getattr(one, "exceptions", None) or ())) if other is not None)
    return "".join(te.format()).rstrip("\n")


_OPS = {
    ast.Eq: "==",
    ast.NotEq: "!=",
    ast.Lt: "<",
    ast.LtE: "<=",
    ast.Gt: ">",
    ast.GtE: ">=",
    ast.Is: "is",
    ast.IsNot: "is not",
    ast.In: "in",
    ast.NotIn: "not in",
}


def _short(value):
    text = repr(value)
    return text if len(text) <= 120 else text[:117] + "..."


def explain(e):
    """
    What a failed `assert` compared, as pytest shows it: `assert 2 == 3`, and where a value
    came from a call. None when it cannot tell. The assert's parts are evaluated again, after
    the failure, in the names of the frame that failed, with their output thrown away.
    """
    if not isinstance(e, AssertionError) or e.args or e.__traceback__ is None:
        return None
    tb = e.__traceback__
    while tb.tb_next:
        tb = tb.tb_next
    frame, line = tb.tb_frame, tb.tb_lineno
    source = "".join(linecache.getlines(frame.f_code.co_filename))
    try:
        tree = ast.parse(source)
    except SyntaxError:
        return None
    node = next((n for n in ast.walk(tree) if isinstance(n, ast.Assert) and n.lineno <= line <= (n.end_lineno or n.lineno)), None)
    if node is None:
        return None
    scope = {**frame.f_globals, **frame.f_locals}
    wheres = []

    def value(expr):
        result = eval(compile(ast.Expression(expr), "<assert>", "eval"), scope)
        if isinstance(expr, ast.Call):
            wheres.append(f" +  where {_short(result)} = {ast.get_source_segment(source, expr)}")
        return result

    try:
        with contextlib.redirect_stdout(io.StringIO()), contextlib.redirect_stderr(io.StringIO()):
            test = node.test
            if isinstance(test, ast.Compare) and len(test.ops) == 1:
                left, right = value(test.left), value(test.comparators[0])
                said = f"assert {_short(left)} {_OPS[type(test.ops[0])]} {_short(right)}"
            elif isinstance(test, ast.UnaryOp) and isinstance(test.op, ast.Not):
                said = f"assert not {_short(value(test.operand))}"
            else:
                said = f"assert {_short(value(test))}"
    except Exception:
        return None
    return "\n".join([said, *wheres])


def _failed_in(e, filename):
    tb = e.__traceback__
    while tb is not None and tb.tb_next is not None:
        tb = tb.tb_next
    return tb is not None and tb.tb_frame.f_code.co_filename == filename


async def _execute(code, source, names, filename):
    """
    Runs `code` in `names` as the file `filename`, awaiting at its top level as Pyodide's
    eval_code_async does. `source` is the code as the learner wrote it, which a traceback
    shows: runner.js changed it only where it awaits `asyncio.run()`, in the same columns.
    """
    source = code if source is None else source
    try:
        compiled = compile(textwrap.dedent(code), filename, "exec", flags=ast.PyCF_ALLOW_TOP_LEVEL_AWAIT, dont_inherit=True)
    except SyntaxError as e:
        lines = source.splitlines()
        if e.filename == filename and e.lineno and 0 < e.lineno <= len(lines):
            e.text = lines[e.lineno - 1] + "\n"
        raise
    lines = source.splitlines(True)
    # As linecache reads a file: every line ends with a newline (tracebacks count on it).
    if lines and not lines[-1].endswith("\n"):
        lines[-1] += "\n"
    linecache.cache[filename] = (len(source), None, lines, filename)
    coroutine = eval(compiled, names)
    if coroutine is not None:
        await coroutine


async def run(code, filename="solution.py", after=None, files=None, cwd="", collect=False, module=None, source=None, after_source=None):
    """
    Runs `code` as the program `filename` beside `files`, from the folder `cwd`, then `after` —
    a check's asserts — with the program's names. With `module` (`pkg.app`) it runs as
    `python -m` runs it: its package is imported first, and its relative imports work. Returns
    (exit status, traceback or None, and with `collect` the folder's files after the run).
    `source` and `after_source` are the two as written, before runner.js awaited their runs.
    """
    files = files.to_py() if hasattr(files, "to_py") else dict(files or {})
    _prepare(files, filename, cwd or "", module)
    names = {"__name__": "__main__", "__builtins__": builtins}
    if filename in files:
        names["__file__"] = os.path.join(APP, filename)
    status, error = 0, None
    _TASK_NUMBERS[0] = itertools.count(1)
    before = asyncio.all_tasks()
    loop = asyncio.get_running_loop()
    handler, factory = loop.get_exception_handler(), loop.get_task_factory()
    # A SystemExit a task of the program raises reaches the event loop: not the host's page.
    loop._system_exit_handler = lambda code: None
    loop._keyboard_interrupt_handler = lambda: None
    try:
        if module:
            package = module.rpartition(".")[0]
            if package:
                importlib.import_module(package)
            names["__package__"] = package
            names["__spec__"] = importlib.util.find_spec(module)
        await _execute(code, source, names, filename)
        if after is not None:
            await _execute(after, after_source, names, CHECK)
    except SystemExit as e:
        status = _exit_status(e)
    except BaseException as e:
        # A check's assert says what it compared, as pytest would; a program's, as Python does.
        why = explain(e) if _failed_in(e, CHECK) else None
        if why:
            e.args = (why,)
        status, error = 1, shown(e)
    finally:
        await _end_tasks(before)
        loop.set_exception_handler(handler)
        loop.set_task_factory(factory)
        # What the program printed is written where it went, and the output is the run's again.
        for stream in (sys.stdout, sys.stderr):
            with contextlib.suppress(Exception):
                stream.flush()
        streams = (sys.stdin, sys.stdout, sys.stderr)
        sys.stdin, sys.stdout, sys.stderr = _STREAMS
        # The program ends: its names go, and what they held is finalized now, in its own
        # output, not during the next run.
        names.clear()
        gc.collect()
        _restore()
        # A file the program printed into closes once its warnings settings are gone, as at exit.
        del streams
        sys.stdout.flush()
        sys.stderr.flush()
    return status, error, (_files() if collect else None)

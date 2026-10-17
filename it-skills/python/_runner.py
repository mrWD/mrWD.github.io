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
import io
import linecache
import os
import shutil
import sys
import threading
import traceback

from pyodide.code import eval_code_async

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
    # turns `asyncio.run()` outside functions into `await`. Inside a function, Python's own
    # message for a call from a running loop.
    if asyncio.iscoroutine(main):
        main.close()
    raise RuntimeError("asyncio.run() cannot be called from a running event loop")


asyncio.run = _asyncio_run


def _clear(folder):
    for name in os.listdir(folder):
        path = os.path.join(folder, name)
        if os.path.isdir(path) and not os.path.islink(path):
            shutil.rmtree(path)
        else:
            os.remove(path)


def _prepare(files, filename, cwd):
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
    sys.path[:] = [os.path.dirname(os.path.join(APP, filename))] + _SYS_PATH
    sys.argv[:] = [filename]
    folder = os.path.join(APP, cwd)
    if os.path.isdir(folder):
        os.chdir(folder)


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
    """The traceback as Python prints it, from the learner's first frame on."""
    te = traceback.TracebackException.from_exception(e)
    stack = list(te.stack)
    while stack and stack[0].filename.startswith("/lib/"):
        stack.pop(0)
    te.stack = traceback.StackSummary.from_list(stack)
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


async def run(code, filename="solution.py", after=None, files=None, cwd="", collect=False):
    """
    Runs `code` as the program `filename` beside `files`, from the folder `cwd`, then `after` —
    a check's asserts — with the program's names. Returns (exit status, traceback or None, and
    with `collect` the folder's files after the run).
    """
    files = files.to_py() if hasattr(files, "to_py") else dict(files or {})
    _prepare(files, filename, cwd or "")
    names = {"__name__": "__main__", "__builtins__": builtins}
    if filename in files:
        names["__file__"] = os.path.join(APP, filename)
    status, error = 0, None
    try:
        await eval_code_async(code, names, filename=filename, return_mode="none")
        if after is not None:
            await eval_code_async(after, names, filename=CHECK, return_mode="none")
    except SystemExit as e:
        status = _exit_status(e)
    except BaseException as e:
        # A check's assert says what it compared, as pytest would; a program's, as Python does.
        why = explain(e) if _failed_in(e, CHECK) else None
        if why:
            e.args = (why,)
        status, error = 1, shown(e)
    finally:
        # The program ends: its names go, and what they held is finalized now, in its own
        # output, not during the next run.
        names.clear()
        gc.collect()
        sys.stdout.flush()
        sys.stderr.flush()
    return status, error, (_files() if collect else None)

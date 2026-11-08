/**
 * Runs a learner's Python in Pyodide — CPython compiled to WebAssembly, so a program prints
 * exactly what Python prints. One copy of these rules serves every host: the phone's hidden
 * WebView (python-host.html), the browser's worker (worker.js) and Node, which runs the
 * course checks. Plain JavaScript, loaded as a script: it defines `PythonRunner`.
 *
 * The rules themselves are Python, in the files beside this one: `_runner.py` (how a program
 * runs) and `pytest.py` (a small pytest). They are installed in the runtime's site-packages.
 */
(function (root) {
  'use strict';

  var MODULES = ['_runner.py', 'pytest.py'];

  /**
   * What a program may import beyond the standard library, by the name it imports: the packages
   * that ship with the app (plugins/with-python.js), loaded from beside the runtime the first
   * time a program needs one. Their own dependencies come with them, by Pyodide's lock file.
   */
  var PACKAGES = { numpy: 'numpy', pandas: 'pandas', sklearn: 'scikit-learn', scipy: 'scipy' };

  /**
   * The most a run may print, in bytes (`PYTHON_OUTPUT_LIMIT` in src/engine/runners/python.ts,
   * docs/LANGUAGE-PACKS.md, rule 4). Past it the write fails, which ends a program that prints
   * in a loop; one that catches the error and goes on is stopped by its time limit. The result
   * keeps the start of the output and says it was cut.
   */
  var OUTPUT_LIMIT = 1024 * 1024;

  /**
   * Pyodide cannot block on `asyncio.run()` in a browser, but it awaits at the top level of a
   * program: there `asyncio.run(main())` becomes `await  __ar(main())`, which runs `main()` as
   * the task asyncio.run makes of it (`__ar` is a built-in of _runner.py). Only the call's
   * first 12 characters change, for 12 others, so every line and column stays: an error's
   * carets point at the learner's code, which the traceback shows (the runner is given the
   * program as written). Not inside a `def`, a `class`, a `lambda`, a string or a comment.
   */
  var RUN = 'asyncio.run(';

  function awaitTopLevelRuns(code) {
    var out = '';
    var copied = 0;
    var lines = logicalLines(code);
    // The indentation of each `def` / `class` the line is inside: no `await` can go there.
    var blocks = [];
    for (var l = 0; l < lines.length; l++) {
      var start = lines[l][0];
      var end = lines[l][1];
      var text = code.slice(start, end);
      var indent = /^[ \t]*/.exec(text)[0].length;
      var first = text.charAt(indent);
      if (first === '' || first === '\n' || first === '\r' || first === '#') continue;
      while (blocks.length && indent <= blocks[blocks.length - 1]) blocks.pop();
      if (/^(async[ \t]+def|def|class)\b/.test(text.slice(indent))) {
        blocks.push(indent);
        continue;
      }
      if (blocks.length) continue;
      var calls = runsIn(code, start, end);
      for (var c = 0; c < calls.length; c++) {
        var at = calls[c][0];
        var close = calls[c][1];
        var trailer = /^[ \t]*[.[(]/.test(code.slice(close + 1, end));
        // `asyncio.run(x).y` needs brackets around the await: `(await __ar(x)).y`.
        out += code.slice(copied, at) + (trailer ? '(await __ar(' : 'await  __ar(') + code.slice(at + RUN.length, close) + (trailer ? '))' : ')');
        copied = close + 1;
      }
    }
    return out + code.slice(copied);
  }

  /** The end of the string literal that opens at `i` (a quote, maybe tripled), past escapes. */
  function stringEnd(code, i) {
    var q = code[i];
    var triple = code.substr(i, 3) === q + q + q;
    var j = i + (triple ? 3 : 1);
    while (j < code.length) {
      if (code[j] === '\\') j += 2;
      else if (triple ? code.substr(j, 3) === q + q + q : code[j] === q) return j + (triple ? 3 : 1);
      else if (!triple && code[j] === '\n') return j;
      else j++;
    }
    return code.length;
  }

  /** The program's logical lines, as [start, end): a line goes on inside brackets, a string or after `\`. */
  function logicalLines(code) {
    var lines = [];
    var start = 0;
    var depth = 0;
    for (var i = 0; i < code.length; i++) {
      var c = code[i];
      if (c === '"' || c === "'") i = stringEnd(code, i) - 1;
      else if (c === '#') {
        while (i + 1 < code.length && code[i + 1] !== '\n') i++;
      } else if (c === '\\' && code[i + 1] === '\n') i++;
      else if (c === '(' || c === '[' || c === '{') depth++;
      else if ((c === ')' || c === ']' || c === '}') && depth > 0) depth--;
      else if (c === '\n' && depth === 0) {
        lines.push([start, i + 1]);
        start = i + 1;
      }
    }
    if (start < code.length) lines.push([start, code.length]);
    return lines;
  }

  /**
   * The `asyncio.run(…)` calls in code[start, end), as [index of the call, index of its closing
   * bracket]: outside strings, comments and lambdas, and not `x.asyncio.run(`.
   */
  function runsIn(code, start, end) {
    var calls = [];
    var depth = 0;
    // The bracket depth of a lambda whose body goes on, or -1.
    var lambda = -1;
    for (var i = start; i < end; i++) {
      var c = code[i];
      if (c === '"' || c === "'") {
        i = stringEnd(code, i) - 1;
        continue;
      }
      if (c === '#') {
        while (i + 1 < end && code[i + 1] !== '\n') i++;
        continue;
      }
      if (c === '(' || c === '[' || c === '{') depth++;
      else if (c === ')' || c === ']' || c === '}') {
        depth--;
        if (depth < lambda) lambda = -1;
      } else if (c === ',' && depth === lambda) lambda = -1;
      var word = i === start || !/[\w.]/.test(code[i - 1]);
      if (word && lambda === -1 && /^lambda\b/.test(code.slice(i, i + 7))) lambda = depth;
      if (word && lambda === -1 && code.substr(i, RUN.length) === RUN) {
        var close = closing(code, i + RUN.length - 1, end);
        if (close === -1) continue;
        calls.push([i, close]);
        i = close;
      }
    }
    return calls;
  }

  /** The index of the bracket that closes the one at `open`, past strings, before `end`; -1 if none. */
  function closing(code, open, end) {
    var depth = 0;
    for (var i = open; i < end; i++) {
      var c = code[i];
      if (c === '"' || c === "'") i = stringEnd(code, i) - 1;
      else if (c === '#') {
        while (i + 1 < end && code[i + 1] !== '\n') i++;
      } else if (c === '(') depth++;
      else if (c === ')' && --depth === 0) return i;
    }
    return -1;
  }

  /**
   * A runner for this Pyodide. `read(name)` gives the text of one of the Python files beside
   * this one (or a promise of it): each host reads them as it reads the runtime. `hooks.loading`
   * and `hooks.loaded` hear when a run waits for packages to load (`loading` with their names) —
   * seconds the first time, which a host does not count against the program's own time.
   */
  async function create(pyodide, read, hooks) {
    var bytes = [];
    var cut = false;
    // While Python's own buffers drain after a cut: what they hold goes nowhere.
    var discarding = false;
    var decoder = new TextDecoder();
    // Like a terminal, the output shows both streams; input() reads the end of the input.
    var collect = {
      isatty: true,
      write: function (buffer) {
        if (discarding) return buffer.length;
        var room = OUTPUT_LIMIT - bytes.length;
        for (var i = 0; i < buffer.length && i < room; i++) bytes.push(buffer[i]);
        if (buffer.length > room) {
          cut = true;
          // An errno Pyodide knows becomes an OSError in Python, quietly: File too large.
          var full = new Error('the output limit of ' + OUTPUT_LIMIT + ' bytes is reached');
          full.code = 'EFBIG';
          throw full;
        }
        return buffer.length;
      },
    };
    pyodide.setStdout(collect);
    pyodide.setStderr(collect);
    pyodide.setStdin({
      stdin: function () {
        return undefined;
      },
    });
    var site = pyodide.runPython('import site\nsite.getsitepackages()[0]');
    for (var i = 0; i < MODULES.length; i++) pyodide.FS.writeFile(site + '/' + MODULES[i], await read(MODULES[i]));
    var runner = pyodide.pyimport('_runner');
    var findImports = pyodide.pyimport('pyodide.code').find_imports;
    var loaded = {};

    /** The packages a request's code imports that are not loaded yet, and the modules it imports from them. */
    function wanted(request) {
      var sources = [request.code || '', request.after || ''];
      var files = request.files || {};
      for (var file in files) if (/\.py$/.test(file)) sources.push(files[file]);
      var names = [];
      var modules = [];
      for (var i = 0; i < sources.length; i++) {
        var found;
        try {
          var proxy = findImports(sources[i]);
          found = proxy.toJs();
          proxy.destroy();
        } catch (e) {
          // Code that does not parse imports nothing yet: running it reports the error.
          continue;
        }
        for (var j = 0; j < found.length; j++) {
          var module = String(found[j]);
          var name = PACKAGES[module.split('.')[0]];
          if (!name || loaded[module]) continue;
          if (!loaded[name] && names.indexOf(name) === -1) names.push(name);
          if (modules.indexOf(module) === -1) modules.push(module);
        }
      }
      return { names: names, modules: modules };
    }

    /**
     * Empties what Python's streams still hold after a cut — the failed write left it in their
     * buffers — so the next run does not start by printing the end of this one.
     */
    function drain() {
      discarding = true;
      try {
        pyodide.runPython('import sys\nfor _s in (sys.__stdout__, sys.__stderr__, sys.stdout, sys.stderr):\n    try:\n        _s.flush()\n    except Exception:\n        pass\ndel _s');
      } catch (e) {
        // Nothing left to drain.
      } finally {
        discarding = false;
      }
    }

    function takeOutput() {
      var text = decoder.decode(new Uint8Array(bytes));
      bytes = [];
      return text;
    }

    /**
     * Runs `code` as the program `filename` beside `files`, from the folder `cwd`, then
     * `after` (a check's asserts) with its names; with `module`, as `python -m` runs it. Resolves with what the program printed, its
     * exit status, the traceback if it failed and, with `collect`, the folder's files after.
     */
    async function run(request) {
      var want = wanted(request);
      if (want.modules.length) {
        // The packages the run waits for, as a learner knows them: `sklearn` is scikit-learn.
        var shown = [];
        want.modules.forEach(function (module) {
          var name = PACKAGES[module.split('.')[0]];
          if (shown.indexOf(name) === -1) shown.push(name);
        });
        if (hooks && hooks.loading) hooks.loading(request, shown);
        try {
          if (want.names.length) await pyodide.loadPackage(want.names, { messageCallback: function () {}, errorCallback: function () {} });
          want.names.forEach(function (name) {
            loaded[name] = true;
          });
          // Importing scikit-learn the first time takes seconds of its own: done here, the
          // program's import finds the module ready, and its time is its own work.
          want.modules.forEach(function (module) {
            try {
              pyodide.runPython('import ' + module);
              loaded[module] = true;
            } catch (e) {
              // A module that is not there: the program's own import reports it.
            }
          });
        } finally {
          if (hooks && hooks.loaded) hooks.loaded(request);
        }
      }
      bytes = [];
      cut = false;
      var files = pyodide.toPy(request.files || {});
      try {
        var after = request.after ? awaitTopLevelRuns(request.after) : null;
        var result = await runner.run(awaitTopLevelRuns(request.code), request.filename || 'solution.py', after, files, request.cwd || '', !!request.collect, request.module || null, request.code, request.after || null);
        var got = result.toJs({ dict_converter: Object.fromEntries });
        result.destroy();
        if (cut) drain();
        var out = { stdout: takeOutput(), status: got[0] };
        // A run cut at its output limit ended on the failed write, not on its own error.
        if (cut) {
          out.status = 1;
          out.cut = true;
        } else if (got[1] != null) out.error = got[1];
        if (got[2] != null) out.files = got[2];
        return out;
      } catch (e) {
        // The runner itself failed: say so rather than nothing.
        if (cut) {
          drain();
          return { stdout: takeOutput(), status: 1, cut: true };
        }
        return { stdout: takeOutput(), status: 1, error: String((e && e.message) || e) };
      } finally {
        files.destroy();
      }
    }

    return { run: run };
  }

  root.PythonRunner = { create: create, awaitTopLevelRuns: awaitTopLevelRuns, modules: MODULES, packages: PACKAGES, outputLimit: OUTPUT_LIMIT };
})(typeof globalThis !== 'undefined' ? globalThis : self);

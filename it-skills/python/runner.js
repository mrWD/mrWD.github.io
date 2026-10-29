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
   * Pyodide cannot block on `asyncio.run()` in a browser, but it awaits at the top level of a
   * program: `asyncio.run(main())` outside a function becomes `(await main())`. The line
   * numbers stay, so an error still points at the learner's line.
   */
  function awaitTopLevelRuns(code) {
    var lines = code.split('\n');
    // The indentation of each `def` / `class` the line is inside: no `await` can go there.
    var blocks = [];
    for (var i = 0; i < lines.length; i++) {
      var line = lines[i];
      if (!line.trim() || /^\s*#/.test(line)) continue;
      var indent = /^[ \t]*/.exec(line)[0].length;
      while (blocks.length && indent <= blocks[blocks.length - 1]) blocks.pop();
      if (/^[ \t]*(async[ \t]+def|def|class)\b/.test(line)) blocks.push(indent);
      else if (!blocks.length) lines[i] = awaitRuns(line);
    }
    return lines.join('\n');
  }

  function awaitRuns(line) {
    var at = line.indexOf('asyncio.run(');
    while (at !== -1) {
      var open = at + 'asyncio.run'.length;
      var close = closing(line, open);
      if (close === -1) return line;
      line = line.slice(0, at) + '(await ' + line.slice(open + 1, close) + ')' + line.slice(close + 1);
      at = line.indexOf('asyncio.run(', at);
    }
    return line;
  }

  /** The index of the bracket that closes the one at `open`, past strings; -1 if not on the line. */
  function closing(line, open) {
    var depth = 0;
    var quote = null;
    for (var i = open; i < line.length; i++) {
      var c = line[i];
      if (quote) {
        if (c === '\\') i++;
        else if (c === quote) quote = null;
      } else if (c === '"' || c === "'") quote = c;
      else if (c === '(') depth++;
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
    var decoder = new TextDecoder();
    // Like a terminal, the output shows both streams; input() reads the end of the input.
    var collect = {
      isatty: true,
      write: function (buffer) {
        for (var i = 0; i < buffer.length; i++) bytes.push(buffer[i]);
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

    function takeOutput() {
      var text = decoder.decode(new Uint8Array(bytes));
      bytes = [];
      return text;
    }

    /**
     * Runs `code` as the program `filename` beside `files`, from the folder `cwd`, then
     * `after` (a check's asserts) with its names. Resolves with what the program printed, its
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
      var files = pyodide.toPy(request.files || {});
      try {
        var after = request.after ? awaitTopLevelRuns(request.after) : null;
        var result = await runner.run(awaitTopLevelRuns(request.code), request.filename || 'solution.py', after, files, request.cwd || '', !!request.collect);
        var got = result.toJs({ dict_converter: Object.fromEntries });
        result.destroy();
        var out = { stdout: takeOutput(), status: got[0] };
        if (got[1] != null) out.error = got[1];
        if (got[2] != null) out.files = got[2];
        return out;
      } catch (e) {
        // The runner itself failed: say so rather than nothing.
        return { stdout: takeOutput(), status: 1, error: String((e && e.message) || e) };
      } finally {
        files.destroy();
      }
    }

    return { run: run };
  }

  root.PythonRunner = { create: create, awaitTopLevelRuns: awaitTopLevelRuns, modules: MODULES, packages: PACKAGES };
})(typeof globalThis !== 'undefined' ? globalThis : self);

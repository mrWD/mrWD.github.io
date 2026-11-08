/**
 * Checks a learner's TypeScript with TypeScript's own compiler — the `typescript` package, 6.0.3,
 * pinned — the way `tsc` checks it, and turns it into the JavaScript the app's runner runs. One
 * copy of these rules serves every host: the phone's hidden WebView (typescript-host.html), the
 * browser's worker (worker.js) and Node, which runs the course checks (scripts/typescript-node.ts).
 * Plain JavaScript, loaded as a script: it defines `TypeScriptChecker`.
 *
 * A request is one of two:
 * - `check`: the files compiled as `tsc` compiles them in their folder — by its tsconfig.json when
 *   it has one, else every TypeScript file with the default options, which a first line
 *   `// tsconfig: "flag": value, …` changes. The answer is the compiler's diagnostics as tsc reports
 *   them (syntax errors first: with one, the types are not checked), and with `emit` the
 *   JavaScript of every file as CommonJS, for the runner.
 * - `tsc`: the command line itself, for a terminal: `tsc`'s own code on the folder's files, which
 *   prints what it prints and writes what it writes (`--init`, `--noEmit`, `-p`, `--outDir`…).
 *
 * Both print the order of types TypeScript 7 prints (`stableTypeOrdering`), which the lessons
 * quote, and take the default libraries as checked (`skipDefaultLibCheck`: they have no errors,
 * and checking them takes seconds). The libraries are parsed once and kept: the first check pays
 * for it, and says so through `hooks.loading` / `hooks.loaded`.
 */
(function (root) {
  'use strict';

  /** Where the files of a request live, and the compiler's libraries. */
  var APP = '/app';
  var LIB = '/typescript/lib';
  var TS_FILE = /\.(c|m)?tsx?$/;
  var ANSI = /\u001b\[[0-9;]*[A-Za-z]/g;
  var FORCED = { stableTypeOrdering: true, skipDefaultLibCheck: true };
  var CATEGORY = ['warning', 'error', 'suggestion', 'message'];

  function normalize(path) {
    var parts = [];
    path.split('/').forEach(function (part) {
      if (part === '' || part === '.') return;
      if (part === '..') parts.pop();
      else parts.push(part);
    });
    return '/' + parts.join('/');
  }

  function join(dir, path) {
    return normalize(path.charAt(0) === '/' ? path : dir + '/' + path);
  }

  function dirname(path) {
    var i = path.lastIndexOf('/');
    return i <= 0 ? '/' : path.slice(0, i);
  }

  function basename(path) {
    return path.slice(path.lastIndexOf('/') + 1);
  }

  /** A path inside the request's folder, as the request names it: `src/index.ts`. */
  function inApp(path) {
    return path.indexOf(APP + '/') === 0 ? path.slice(APP.length + 1) : undefined;
  }

  /** The request's files by absolute path, the libraries beside them, and what was written. */
  function Disk(files, libs, cwd) {
    this.cwd = cwd;
    this.files = new Map();
    for (var name in files) this.files.set(join(APP, name), files[name]);
    this.libs = libs;
    this.written = {};
    this.removed = [];
    this.times = new Map();
  }

  Disk.prototype.read = function (path) {
    path = join(this.cwd, path);
    if (this.files.has(path)) return this.files.get(path);
    if (dirname(path) === LIB && Object.prototype.hasOwnProperty.call(this.libs, basename(path))) return this.libs[basename(path)];
    return undefined;
  };

  Disk.prototype.exists = function (path) {
    return this.read(path) !== undefined;
  };

  Disk.prototype.isDir = function (path) {
    path = join(this.cwd, path);
    if (path === '/' || path === APP || path === LIB || path === dirname(LIB)) return true;
    var prefix = path + '/';
    for (var name of this.files.keys()) if (name.indexOf(prefix) === 0) return true;
    return false;
  };

  /** What a folder holds: its files' and folders' names. */
  Disk.prototype.entries = function (dir) {
    dir = join(this.cwd, dir);
    var files = [];
    var directories = new Set();
    if (dir === LIB) files = Object.keys(this.libs);
    if (dir === '/') directories.add(APP.slice(1)).add(dirname(LIB).slice(1));
    if (dir === dirname(LIB)) directories.add(basename(LIB));
    var prefix = dir === '/' ? '/' : dir + '/';
    for (var name of this.files.keys()) {
      if (name.indexOf(prefix) !== 0) continue;
      var rest = name.slice(prefix.length);
      var slash = rest.indexOf('/');
      if (slash === -1) files.push(rest);
      else directories.add(rest.slice(0, slash));
    }
    return { files: files.sort(), directories: Array.from(directories).sort() };
  };

  /**
   * When a file last changed, for `tsc -b`. A terminal keeps no clock between commands, so the
   * folder's sources count as newer than everything else, and what this run writes as newer
   * still: a build looks at the contents its .tsbuildinfo remembers to tell whether a project is
   * up to date, as it does after a `touch`.
   */
  Disk.prototype.modified = function (path) {
    path = join(this.cwd, path);
    if (!this.exists(path)) return undefined;
    if (this.times.has(path)) return this.times.get(path);
    return new Date(TS_FILE.test(path) && !/\.d\.(c|m)?ts$/.test(path) ? 2000 : 1000);
  };

  Disk.prototype.touch = function (path, time) {
    this.times.set(join(this.cwd, path), time || new Date(3000 + this.times.size));
  };

  Disk.prototype.write = function (path, text) {
    path = join(this.cwd, path);
    this.touch(path);
    this.files.set(path, text);
    var name = inApp(path);
    if (name !== undefined) this.written[name] = text;
  };

  Disk.prototype.remove = function (path) {
    path = join(this.cwd, path);
    this.files.delete(path);
    var name = inApp(path);
    if (name !== undefined) {
      delete this.written[name];
      this.removed.push(name);
    }
  };

  /** A `ts.System` over the request's files: what `tsc`'s own code reads, writes and prints. */
  function system(ts, disk, cwd, out) {
    var sys = {
      args: [],
      newLine: '\n',
      useCaseSensitiveFileNames: true,
      status: 0,
      write: function (s) {
        out.push(s);
      },
      // A terminal: tsc prints errors with the line they are on, as it does in one.
      writeOutputIsTTY: function () {
        return true;
      },
      readFile: function (path) {
        return disk.read(path);
      },
      writeFile: function (path, data) {
        disk.write(path, data);
      },
      resolvePath: function (path) {
        return path;
      },
      fileExists: function (path) {
        return disk.exists(path);
      },
      directoryExists: function (path) {
        return disk.isDir(path);
      },
      createDirectory: function () {},
      getExecutingFilePath: function () {
        return LIB + '/tsc.js';
      },
      getCurrentDirectory: function () {
        return cwd;
      },
      getDirectories: function (path) {
        return disk.entries(path).directories;
      },
      readDirectory: function (path, extensions, excludes, includes, depth) {
        return ts.matchFiles(path, extensions, excludes, includes, true, cwd, depth, function (dir) {
          return disk.entries(dir);
        }, function (p) {
          return p;
        });
      },
      deleteFile: function (path) {
        disk.remove(path);
      },
      getModifiedTime: function (path) {
        return disk.modified(path);
      },
      setModifiedTime: function (path, time) {
        disk.touch(path, time);
      },
      realpath: function (path) {
        return path;
      },
      getEnvironmentVariable: function () {
        return '';
      },
      exit: function (code) {
        sys.status = code === undefined ? 0 : code;
      },
    };
    return sys;
  }

  /**
   * The compiler options of a first line `// tsconfig: "strict": false, "target": "es2022"` —
   * the options a lesson's code is compiled with, which the learner sees. Errors go with them.
   */
  function firstLineOptions(ts, text, fileName, cwd) {
    var m = /^\/\/\s*tsconfig:\s*(.*)$/.exec(text.split('\n')[0]);
    if (!m) return { options: {}, errors: [] };
    var json;
    try {
      json = JSON.parse('{' + m[1].replace(/,\s*$/, '') + '}');
    } catch (e) {
      var file = ts.createSourceFile(fileName, text, ts.ScriptTarget.Latest);
      return {
        options: {},
        errors: [{ file: file, start: 0, length: m[0].length, category: ts.DiagnosticCategory.Error, code: 5024, messageText: 'The first line "// tsconfig: …" is not JSON: ' + e.message }],
      };
    }
    return ts.convertCompilerOptionsFromJson(json, cwd);
  }

  /** What one diagnostic says, as plain data: where, which error, and its whole message. */
  function plain(ts, d, cwd) {
    var out = { code: d.code, category: CATEGORY[d.category] || 'error', message: ts.flattenDiagnosticMessageText(d.messageText, '\n') };
    if (d.file && d.start !== undefined) {
      var at = d.file.getLineAndCharacterOfPosition(d.start);
      out.file = relative(cwd, d.file.fileName);
      out.line = at.line + 1;
      out.column = at.character + 1;
    }
    return out;
  }

  function relative(cwd, path) {
    if (path.indexOf(cwd + '/') === 0) return path.slice(cwd.length + 1);
    var from = cwd.split('/').filter(Boolean);
    var to = path.split('/').filter(Boolean);
    var i = 0;
    while (i < from.length && i < to.length && from[i] === to[i]) i++;
    return from.slice(i).map(function () {
      return '..';
    }).concat(to.slice(i)).join('/');
  }

  /** The JavaScript a TypeScript file becomes, by the path it is written to beside it. */
  function jsName(name) {
    return name.replace(/\.mts$/, '.mjs').replace(/\.cts$/, '.cjs').replace(TS_FILE, '.js');
  }

  function create(ts, libs, hooks) {
    hooks = hooks || {};
    /** The libraries, parsed once: by file and by the language version a program reads them in. */
    var parsed = new Map();

    function host(disk, cwd, request, state) {
      return {
        getSourceFile: function (fileName, languageVersion) {
          var text = disk.read(fileName);
          if (text === undefined) return undefined;
          if (dirname(fileName) !== LIB) return ts.createSourceFile(fileName, text, languageVersion);
          var key = fileName + '|' + (typeof languageVersion === 'object' ? languageVersion.languageVersion + '|' + languageVersion.impliedNodeFormat : languageVersion);
          var file = parsed.get(key);
          if (!file) {
            if (!state.loading) {
              state.loading = true;
              if (hooks.loading) hooks.loading(request);
            }
            file = ts.createSourceFile(fileName, text, languageVersion);
            parsed.set(key, file);
          }
          return file;
        },
        getDefaultLibFileName: function (options) {
          return LIB + '/' + ts.getDefaultLibFileName(options);
        },
        getDefaultLibLocation: function () {
          return LIB;
        },
        writeFile: function () {},
        getCurrentDirectory: function () {
          return cwd;
        },
        getCanonicalFileName: function (fileName) {
          return fileName;
        },
        useCaseSensitiveFileNames: function () {
          return true;
        },
        getNewLine: function () {
          return '\n';
        },
        fileExists: function (path) {
          return disk.exists(path);
        },
        readFile: function (path) {
          return disk.read(path);
        },
        directoryExists: function (path) {
          return disk.isDir(path);
        },
        getDirectories: function (path) {
          return disk.entries(path).directories;
        },
        realpath: function (path) {
          return path;
        },
        jsDocParsingMode: ts.JSDocParsingMode.ParseForTypeErrors,
      };
    }

    /** The files compiled as `tsc` compiles them in their folder. */
    function check(request) {
      var cwd = join(APP, request.cwd || '');
      var disk = new Disk(request.files || {}, libs, cwd);
      var sys = system(ts, disk, cwd, []);
      var config = cwd + '/tsconfig.json';
      var options;
      var roots;
      var configErrors = [];
      if (disk.exists(config)) {
        var unrecoverable = [];
        var line = ts.getParsedCommandLineOfConfigFile(config, {}, {
          useCaseSensitiveFileNames: true,
          readDirectory: sys.readDirectory,
          fileExists: sys.fileExists,
          readFile: sys.readFile,
          getCurrentDirectory: sys.getCurrentDirectory,
          onUnRecoverableConfigFileDiagnostic: function (d) {
            unrecoverable.push(d);
          },
        });
        if (!line) return report(unrecoverable, cwd, null);
        options = line.options;
        roots = line.fileNames;
        configErrors = ts.getConfigFileParsingDiagnostics(line).slice();
      } else {
        options = {};
        roots = [];
        for (var name of disk.files.keys()) if (name.indexOf(cwd + '/') === 0 && TS_FILE.test(name)) roots.push(name);
        roots.sort();
        roots.forEach(function (file) {
          var first = firstLineOptions(ts, disk.read(file), file, cwd);
          Object.assign(options, first.options);
          configErrors = configErrors.concat(first.errors);
        });
      }
      (request.roots || []).forEach(function (name) {
        var file = join(cwd, name);
        if (roots.indexOf(file) === -1) roots.push(file);
      });
      options = Object.assign({}, options, FORCED);
      // A check's own file sits beside tsconfig.json, outside a `rootDir: "src"`: it only checks, it is never written.
      if (request.roots && request.roots.length) options.rootDir = undefined;
      var state = { loading: false };
      var program = ts.createProgram({ rootNames: roots, options: options, host: host(disk, cwd, request, state), configFileParsingDiagnostics: configErrors });
      if (state.loading && hooks.loaded) hooks.loaded(request);
      // As tsc reports them: with a syntax error, the types are not checked.
      var all = program.getConfigFileParsingDiagnostics().slice();
      var configured = all.length;
      all = all.concat(program.getSyntacticDiagnostics());
      if (all.length === configured) {
        all = all.concat(program.getOptionsDiagnostics(), program.getGlobalDiagnostics());
        if (all.length === configured) all = all.concat(program.getSemanticDiagnostics());
        if (options.declaration && all.length === configured) all = all.concat(program.getDeclarationDiagnostics());
      }
      var result = report(ts.sortAndDeduplicateDiagnostics(all), cwd, program);
      if (request.emit) result.js = emit(program, options, cwd);
      return result;
    }

    function report(diagnostics, cwd, program) {
      var format = {
        getCurrentDirectory: function () {
          return cwd;
        },
        getCanonicalFileName: function (f) {
          return f;
        },
        getNewLine: function () {
          return '\n';
        },
      };
      return {
        diagnostics: diagnostics.map(function (d) {
          return plain(ts, d, cwd);
        }),
        text: ts.formatDiagnostics(diagnostics, format).replace(/\n$/, ''),
        files: program
          ? program
              .getRootFileNames()
              .map(function (f) {
                return relative(cwd, f);
              })
          : [],
      };
    }

    /**
     * Every file of the program as JavaScript the app's runner can run: CommonJS beside its
     * source, `./x.ts` imports pointing at `./x.js`. Types are erased file by file, as a bundler
     * or Node.js erases them; what the options say about the target stays.
     */
    function emit(program, options, cwd) {
      var run = Object.assign({}, options, {
        module: ts.ModuleKind.CommonJS,
        moduleResolution: undefined,
        verbatimModuleSyntax: false,
        rewriteRelativeImportExtensions: true,
        preserveConstEnums: true,
        importHelpers: false,
        noEmitHelpers: false,
        sourceMap: false,
        inlineSourceMap: false,
        declaration: false,
        noEmit: false,
        outDir: undefined,
        rootDir: undefined,
      });
      var js = {};
      program.getRootFileNames().forEach(function (file) {
        if (/\.d\.(c|m)?ts$/.test(file) || !TS_FILE.test(file)) return;
        var source = program.getSourceFile(file);
        if (!source) return;
        var out = ts.transpileModule(source.text, { compilerOptions: run, fileName: file, reportDiagnostics: false });
        js[jsName(relative(cwd, file))] = out.outputText;
      });
      return js;
    }

    /** `tsc` with these arguments, in the request's folder. */
    function tsc(request) {
      var cwd = join(APP, request.cwd || '');
      var disk = new Disk(request.files || {}, libs, cwd);
      var out = [];
      var sys = system(ts, disk, cwd, out);
      var args = (request.args || []).slice();
      var compiles = !args.some(function (a) {
        return /^--?(b|build|init|showConfig|v|version|h|help|all|\?)$/i.test(a);
      });
      if (compiles) args.push('--stableTypeOrdering', '--skipDefaultLibCheck');
      try {
        ts.executeCommandLine(sys, function () {}, args);
      } catch (e) {
        out.push(String(e && e.stack ? e.stack : e));
        sys.status = 1;
      }
      return { stdout: out.join('').replace(ANSI, '').replace(/\n+$/, ''), status: sys.status, written: disk.written, removed: disk.removed };
    }

    return {
      version: ts.version,
      run: function (request) {
        try {
          return request.mode === 'tsc' ? tsc(request) : check(request);
        } catch (e) {
          return { error: String(e && e.stack ? e.stack : e) };
        }
      },
    };
  }

  root.TypeScriptChecker = { create: create, LIB: LIB };
})(typeof globalThis !== 'undefined' ? globalThis : typeof self !== 'undefined' ? self : this);

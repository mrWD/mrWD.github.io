/**
 * The browser's Python: Pyodide in a worker, so a program that never ends cannot freeze the
 * page — the app terminates the worker and starts another. Messages: `{ id, code, files,
 * after, filename }` in, `{ type: 'result', id, stdout, status, error }` out, and `loading` /
 * `loaded` while a run waits for packages (`loading` names them).
 */
/* global importScripts, loadPyodide, PythonRunner */
importScripts('pyodide.js', 'runner.js');

var runner = loadPyodide({ indexURL: new URL('./', self.location.href).href }).then(function (pyodide) {
  return PythonRunner.create(
    pyodide,
    function (name) {
      return fetch(new URL(name, self.location.href)).then(function (r) {
        return r.text();
      });
    },
    {
      // Loading numpy or pandas takes seconds the first time: not the program's own time.
      loading: function (request, packages) {
        self.postMessage({ type: 'loading', id: request.id, packages: packages });
      },
      loaded: function (request) {
        self.postMessage({ type: 'loaded', id: request.id });
      },
    },
  );
});

runner.then(
  function () {
    self.postMessage({ type: 'ready' });
  },
  function (e) {
    self.postMessage({ type: 'failed', error: String(e) });
  },
);

self.onmessage = function (event) {
  var request = event.data;
  runner
    .then(function (r) {
      return r.run(request);
    })
    .then(
      function (result) {
        self.postMessage({ type: 'result', id: request.id, stdout: result.stdout, status: result.status, error: result.error, files: result.files });
      },
      function (e) {
        self.postMessage({ type: 'result', id: request.id, stdout: '', status: 1, error: String(e) });
      },
    );
};

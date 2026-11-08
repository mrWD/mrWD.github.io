/**
 * The browser's TypeScript compiler: TypeScript's own compiler in a worker, so a type that takes
 * the compiler long cannot freeze the page — the app terminates the worker and starts another.
 * Messages: `{ id, mode, files, … }` in, `{ type: 'result', id, … }` out, and `loading` /
 * `loaded` while the first check parses the compiler's libraries. What a check does is
 * checker.js, the same file the phone's WebView and Node load.
 */
/* global importScripts, ts, TypeScriptChecker */
importScripts('typescript.js', 'checker.js');

var checker = fetch(new URL('lib.json', self.location.href))
  .then(function (r) {
    if (!r.ok) throw new Error('lib.json: ' + r.status);
    return r.json();
  })
  .then(function (libs) {
    return TypeScriptChecker.create(ts, libs, {
      loading: function (request) {
        self.postMessage({ type: 'loading', id: request.id });
      },
      loaded: function (request) {
        self.postMessage({ type: 'loaded', id: request.id });
      },
    });
  });

checker.then(
  function () {
    self.postMessage({ type: 'ready' });
  },
  function (e) {
    self.postMessage({ type: 'failed', error: String(e) });
  },
);

self.onmessage = function (event) {
  var request = event.data;
  checker.then(
    function (c) {
      self.postMessage(Object.assign({}, c.run(request), { type: 'result', id: request.id }));
    },
    function (e) {
      self.postMessage({ type: 'result', id: request.id, error: String(e) });
    },
  );
};

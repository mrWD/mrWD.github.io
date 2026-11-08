/**
 * What a learner's Python may reach of the page or worker that hosts it: its own runtime's files,
 * nothing else (docs/LANGUAGE-PACKS.md, rule 2). Pyodide gives a program the host's JavaScript
 * through its `js` module, and Python cannot be fenced from inside, so the host itself is sealed
 * before Pyodide loads: Pyodide never holds a reference the program could use to get out.
 *
 *  - `fetch`, `XMLHttpRequest` and `importScripts` serve only addresses under the runtime's folder
 *    (where Pyodide reads its standard library and packages); any other is refused.
 *  - What opens a connection or a context of its own — `WebSocket`, `EventSource`,
 *    `WebTransport`, a nested `Worker` (it would start unsealed), `window.open`,
 *    `navigator.sendBeacon` — throws.
 *  - Storage the app's own pages share with this origin — IndexedDB, the Cache API — is gone.
 *
 * The phone's page adds what a page needs and a worker does not have: a content security policy
 * and, in the app, a WebView that loads nothing outside the runtime's folder
 * (src/components/PythonHost.tsx). Plain JavaScript, loaded as a script: it defines `sealPython`.
 */
(function (root) {
  'use strict';

  function refused(what) {
    return new Error(what + ' is not available to a program here: it reaches nothing outside its runtime');
  }

  /** Seals `scope` (a window or a worker's global) so it reaches only addresses under `base`. */
  function sealPython(scope, base) {
    var prefix = new URL(base, scope.location && scope.location.href).href;
    function inside(input) {
      var href = typeof input === 'string' ? input : input && typeof input.url === 'string' ? input.url : String(input);
      var url;
      try {
        url = new URL(href, scope.location && scope.location.href);
      } catch (e) {
        return false;
      }
      return url.href.indexOf(prefix) === 0 && url.href.indexOf('/../') === -1;
    }
    function define(name, value) {
      try {
        Object.defineProperty(scope, name, { value: value, writable: false, configurable: false });
      } catch (e) {
        scope[name] = value;
      }
    }

    // The originals live only in this closure: nothing a program can reach refers to them.
    var nativeFetch = scope.fetch;
    if (nativeFetch) {
      define('fetch', function fetch(input, init) {
        if (!inside(input)) return Promise.reject(refused('fetch(' + JSON.stringify(String((input && input.url) || input)) + ')'));
        return nativeFetch.call(scope, input, init);
      });
    }
    var XHR = scope.XMLHttpRequest;
    if (XHR) {
      // Patched in place: the prototype's own open is the only one there is.
      var open = XHR.prototype.open;
      Object.defineProperty(XHR.prototype, 'open', {
        value: function (method, url) {
          if (!inside(url)) throw refused('XMLHttpRequest to ' + JSON.stringify(String(url)));
          return open.apply(this, arguments);
        },
        writable: false,
        configurable: false,
      });
    }
    var load = scope.importScripts;
    if (load) {
      define('importScripts', function importScripts() {
        for (var i = 0; i < arguments.length; i++) if (!inside(arguments[i])) throw refused('importScripts(' + JSON.stringify(String(arguments[i])) + ')');
        return load.apply(scope, arguments);
      });
    }
    ['WebSocket', 'EventSource', 'WebTransport', 'Worker', 'SharedWorker', 'RTCPeerConnection'].forEach(function (name) {
      if (name in scope)
        define(name, function () {
          throw refused(name);
        });
    });
    if (scope.open && scope.document) {
      define('open', function () {
        throw refused('window.open');
      });
    }
    if (scope.navigator && scope.navigator.sendBeacon) {
      try {
        Object.defineProperty(scope.navigator, 'sendBeacon', {
          value: function () {
            throw refused('navigator.sendBeacon');
          },
        });
      } catch (e) {
        // A navigator that does not take it has no beacon to send.
      }
    }
    ['indexedDB', 'caches'].forEach(function (name) {
      if (name in scope) define(name, undefined);
    });
  }

  root.sealPython = sealPython;
})(typeof globalThis !== 'undefined' ? globalThis : self);

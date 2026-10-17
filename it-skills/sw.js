/**
 * The web app's service worker, registered by src/app/+html.tsx: the installed app opens offline
 * once it has been opened online. Pages come from the network while it answers and from the cache
 * when it does not; every other file of the app — the bundle, fonts, images, Python — from the
 * cache once fetched. scripts/release-web.sh stamps each build into the cache's name, so a new
 * build starts from an empty cache and the old one is deleted. The server's API is another
 * origin and never cached here: the app keeps the courses and the progress itself.
 */
var BUILD = 'ddea68e-20261017085425';
var CACHE = 'it-skills-' + BUILD;
var SCOPE = new URL(self.registration.scope).pathname;

function keep(request, response) {
  if (response.ok) {
    var copy = response.clone();
    caches.open(CACHE).then(function (cache) {
      return cache.put(request, copy);
    });
  }
  return response;
}

self.addEventListener('install', function (event) {
  event.waitUntil(
    caches
      .open(CACHE)
      .then(function (cache) {
        return cache.add(SCOPE);
      })
      .then(function () {
        return self.skipWaiting();
      }),
  );
});

self.addEventListener('activate', function (event) {
  event.waitUntil(
    caches
      .keys()
      .then(function (keys) {
        return Promise.all(
          keys
            .filter(function (key) {
              return key.indexOf('it-skills-') === 0 && key !== CACHE;
            })
            .map(function (key) {
              return caches.delete(key);
            }),
        );
      })
      .then(function () {
        return self.clients.claim();
      }),
  );
});

self.addEventListener('fetch', function (event) {
  var request = event.request;
  if (request.method !== 'GET') return;
  var url = new URL(request.url);
  if (url.origin !== self.location.origin || url.pathname.indexOf(SCOPE) !== 0) return;
  if (request.mode === 'navigate') {
    // Any page of the app is the same single page: offline, the start page stands in for it.
    event.respondWith(
      fetch(request)
        .then(function (response) {
          return keep(request, response);
        })
        .catch(function () {
          return caches.match(request).then(function (hit) {
            return hit || caches.match(SCOPE);
          });
        }),
    );
    return;
  }
  event.respondWith(
    caches.match(request).then(function (hit) {
      return (
        hit ||
        fetch(request).then(function (response) {
          return keep(request, response);
        })
      );
    }),
  );
});

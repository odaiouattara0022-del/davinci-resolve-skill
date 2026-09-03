/* PyTerm service worker — coque applicative hors-ligne. */
const VERSION = 'pyterm-v1';
const SHELL = [
  './', './index.html', './assets/app.css', './assets/icon.svg',
  './js/fs.js', './js/snippets.js', './js/runtime.js',
  './js/terminal.js', './js/editor.js', './js/main.js',
  './manifest.webmanifest'
];

self.addEventListener('install', (e) => {
  e.waitUntil(
    caches.open(VERSION)
      .then((c) => Promise.allSettled(SHELL.map((u) => c.add(new Request(u, { cache: 'reload' })))))
      .then(() => self.skipWaiting())
  );
});

self.addEventListener('activate', (e) => {
  e.waitUntil(
    caches.keys()
      .then((ks) => Promise.all(ks.filter((k) => k !== VERSION).map((k) => caches.delete(k))))
      .then(() => self.clients.claim())
  );
});

self.addEventListener('fetch', (e) => {
  const req = e.request;
  if (req.method !== 'GET') return;
  const url = new URL(req.url);

  // Le noyau local ne doit jamais etre mis en cache.
  if (url.pathname.startsWith('/exec') || url.pathname.startsWith('/events') ||
      url.pathname.startsWith('/kernel') || url.pathname.startsWith('/fs') ||
      url.pathname.startsWith('/packages')) return;

  // CDN (CodeMirror, Pyodide) : cache d'abord, reseau en secours, puis memorisation.
  const isCdn = url.hostname.endsWith('cdnjs.cloudflare.com') ||
                url.hostname.endsWith('cdn.jsdelivr.net') ||
                url.hostname.endsWith('fonts.googleapis.com') ||
                url.hostname.endsWith('fonts.gstatic.com');

  if (isCdn) {
    e.respondWith(
      caches.match(req).then((hit) => hit || fetch(req).then((res) => {
        if (res.ok || res.type === 'opaque') {
          const copy = res.clone();
          caches.open(VERSION).then((c) => c.put(req, copy)).catch(() => {});
        }
        return res;
      }))
    );
    return;
  }

  // Coque applicative : reseau d'abord (pour recevoir les mises a jour), cache en secours.
  e.respondWith(
    fetch(req).then((res) => {
      if (res.ok && url.origin === self.location.origin) {
        const copy = res.clone();
        caches.open(VERSION).then((c) => c.put(req, copy)).catch(() => {});
      }
      return res;
    }).catch(() => caches.match(req).then((hit) => hit || caches.match('./index.html')))
  );
});

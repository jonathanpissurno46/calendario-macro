/* Service worker del Calendario Económico Macro.
   Estrategia: red primero para el documento (así recibes las actualizaciones),
   caché primero para iconos y manifiesto. Funciona sin conexión. */
const CACHE = 'calendario-macro-v1';
const ASSETS = ['./', './index.html', './manifest.webmanifest',
                './icon-192.png', './icon-512.png', './apple-touch-icon.png'];

self.addEventListener('install', e => {
  e.waitUntil(caches.open(CACHE).then(c => c.addAll(ASSETS)).then(() => self.skipWaiting()));
});

self.addEventListener('activate', e => {
  e.waitUntil(
    caches.keys()
      .then(ks => Promise.all(ks.filter(k => k !== CACHE).map(k => caches.delete(k))))
      .then(() => self.clients.claim())
  );
});

self.addEventListener('fetch', e => {
  const req = e.request;
  if (req.method !== 'GET') return;
  const url = new URL(req.url);
  if (url.origin !== location.origin) return;

  const esDocumento = req.mode === 'navigate' ||
                      url.pathname.endsWith('/') ||
                      url.pathname.endsWith('index.html');

  if (esDocumento) {
    e.respondWith(
      fetch(req)
        .then(r => { const c = r.clone(); caches.open(CACHE).then(x => x.put(req, c)); return r; })
        .catch(() => caches.match('./index.html'))
    );
    return;
  }
  e.respondWith(
    caches.match(req).then(r => r || fetch(req).then(res => {
      const c = res.clone();
      caches.open(CACHE).then(x => x.put(req, c));
      return res;
    }))
  );
});

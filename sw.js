// Network-first for the game (chunk names repeat across deploys, so never serve them stale while online);
// cache-first only for the version-pinned three.js CDN files. Falls back to cache when offline.
const C = 'arees-v1';
self.addEventListener('install', () => self.skipWaiting());
self.addEventListener('activate', (e) => e.waitUntil(caches.keys().then(k => Promise.all(k.filter(x => x !== C).map(x => caches.delete(x)))).then(() => self.clients.claim())));
self.addEventListener('fetch', (e) => {
  const r = e.request; if (r.method !== 'GET') return;
  const u = new URL(r.url), cdn = u.hostname === 'cdn.jsdelivr.net';
  if (!cdn && u.origin !== location.origin) return;
  e.respondWith(cdn
    ? caches.match(r).then(h => h || fetch(r).then(x => { if (x.ok) { const c = x.clone(); caches.open(C).then(k => k.put(r, c)); } return x; }))
    : fetch(r).then(x => { if (x.ok) { const c = x.clone(); caches.open(C).then(k => k.put(r, c)); } return x; }).catch(() => caches.match(r).then(h => h || caches.match('./'))));
});

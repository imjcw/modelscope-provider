/* Minimal PWA service worker — app-shell cache.
 *
 * Strategy (fixed 2026-08-17):
 *   - Navigation requests (SPA routes like /web/suppliers): NETWORK-FIRST.
 *     Always fetch a fresh index.html; only fall back to the cache when the
 *     network is unavailable. This prevents a stale app shell after a redeploy,
 *     which previously served an old index.html whose hashed assets 404'd
 *     ("Failed to fetch") and kept running an outdated app bundle.
 *   - Static assets (/web/assets/*, same-origin GET): CACHE-FIRST with a
 *     network fallback. Hashed filenames make these safe to cache.
 *   - API requests (/api/*) and anything non-GET / non-/web / cross-origin:
 *     never intercepted — the browser handles them normally so admin API calls
 *     (e.g. saving a model) always hit the live server.
 *   - respondWith never rejects: a failed fetch returns a clean error Response
 *     instead of throwing, so the console stays clean.
 */

const CACHE_NAME = 'ai-provider-v2';
const APP_SHELL = ['/web/', '/web/manifest.json'];

self.addEventListener('install', (event) => {
  // Cache the shell best-effort; a single missing file must not abort install.
  event.waitUntil(
    caches.open(CACHE_NAME).then((cache) => cache.addAll(APP_SHELL).catch(() => {}))
  );
  self.skipWaiting();
});

self.addEventListener('activate', (event) => {
  // Drop every cache except the current one (invalidates stale app shells).
  event.waitUntil(
    caches.keys().then((keys) =>
      Promise.all(keys.filter((k) => k !== CACHE_NAME).map((k) => caches.delete(k)))
    )
  );
  self.clients.claim();
});

self.addEventListener('fetch', (event) => {
  const url = new URL(event.request.url);

  // Only manage same-origin GET requests under /web/. Everything else (API
  // calls under /api/, POST/PUT, cross-origin) is passed straight through.
  if (event.request.method !== 'GET' || url.origin !== self.location.origin) return;
  if (!url.pathname.startsWith('/web/')) return;

  // SPA navigation: network-first, cache fallback when offline.
  if (event.request.mode === 'navigate') {
    event.respondWith(
      (async () => {
        try {
          const response = await fetch(event.request);
          if (response.status === 200) {
            const cache = await caches.open(CACHE_NAME);
            cache.put(event.request, response.clone());
          }
          return response;
        } catch (err) {
          const cached = await caches.match(event.request);
          if (cached) return cached;
          const shell = await caches.match('/web/');
          return shell || new Response('Offline — no cached app shell', {
            status: 503,
            statusText: 'Offline',
            headers: { 'Content-Type': 'text/html' },
          });
        }
      })()
    );
    return;
  }

  // Static assets: cache-first, network fallback, never throw.
  event.respondWith(
    (async () => {
      const cached = await caches.match(event.request);
      if (cached) return cached;
      try {
        const response = await fetch(event.request);
        if (response.status === 200) {
          const cache = await caches.open(CACHE_NAME);
          cache.put(event.request, response.clone());
        }
        return response;
      } catch (err) {
        // Asset was never cached and the network is down: return a clean 504
        // rather than rejecting respondWith (which would surface as a console error).
        return new Response('', { status: 504, statusText: 'Not cached' });
      }
    })()
  );
});

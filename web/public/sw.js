/* Minimal PWA service worker — app-shell cache with stale-while-revalidate.
   Served at /web/sw.js from the build output (copied from public/sw.js). */

const CACHE_NAME = 'ai-provider-v1';
const APP_SHELL = [
  '/web/',
  '/web/manifest.json',
  '/web/icons/icon-192.svg',
  '/web/icons/icon-512.svg',
];

self.addEventListener('install', (event) => {
  event.waitUntil(
    caches.open(CACHE_NAME).then((cache) => cache.addAll(APP_SHELL))
  );
  self.skipWaiting();
});

self.addEventListener('activate', (event) => {
  event.waitUntil(
    caches.keys().then((keys) =>
      Promise.all(keys.filter((k) => k !== CACHE_NAME).map((k) => caches.delete(k)))
    )
  );
  self.clients.claim();
});

self.addEventListener('fetch', (event) => {
  const url = new URL(event.request.url);
  // Let API calls go to network, cache-as-network-races for everything else
  if (url.pathname.startsWith('/web/api/')) {
    event.respondWith(
      fetch(event.request).catch(() => caches.match(event.request))
    );
    return;
  }

  event.respondWith(
    (async () => {
      const cached = await caches.match(event.request);
      if (cached) return cached;
      try {
        const response = await fetch(event.request);
        // Only cache same-origin GETs that succeeded
        if (response.status === 200 && event.request.method === 'GET') {
          const clone = response.clone();
          caches.open(CACHE_NAME).then((cache) => cache.put(event.request, clone));
        }
        return response;
      } catch (err) {
        // Offline fallback: serve the cached app shell for navigation.
        // Always resolve to a real Response so respondWith() never gets undefined.
        if (event.request.mode === 'navigate') {
          const shell = await caches.match('/web/');
          return shell || new Response('Offline — no cached app shell', {
            status: 503,
            statusText: 'Offline',
            headers: { 'Content-Type': 'text/html' }
          });
        }
        // For non-navigation (e.g. an image/icon we never cached), re-throw so
        // the browser can surface the real network error instead of swallowing it.
        throw err;
      }
    })()
  );
});

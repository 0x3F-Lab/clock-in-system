const isDevEnvironment = self.location.hostname === 'localhost' || self.location.hostname === '127.0.0.1';

if (isDevEnvironment) {
  console.log('Running in development mode — disabling caching.');

  // Intercept all fetches and just proxy to the network (no caching)
  self.addEventListener('fetch', event => {
    event.respondWith(fetch(event.request));
  });

} else {
  // Load workbox from CDN
  importScripts('https://storage.googleapis.com/workbox-cdn/releases/6.5.4/workbox-sw.js');

  // Skip waiting to activate the new SW immediately
  self.addEventListener('install', (event) => {
    self.skipWaiting();
  });

  // Claim clients after the service worker is activated
  self.addEventListener('activate', (event) => {
    event.waitUntil(self.clients.claim());
    workbox.navigationPreload.enable();
  });

  // Set custom cache names
  workbox.core.setCacheNameDetails({
    prefix: 'clockinapp',
    suffix: "{{ STATIC_CACHE_VER|default:'v0'|escapejs }}",
  });

  const OFFLINE_URL = '/offline';

  workbox.precaching.precacheAndRoute([
    { url: OFFLINE_URL, revision: null },
    { url: '/static/css/styles.css', revision: null },
    { url: '/static/js/global.js', revision: null },
    { url: '/static/img/logo.png', revision: null },
    { url: '/static/favicon.ico', revision: null },
    { url: '/static/img/favicon/favicon-32x32.png', revision: null },
    { url: '/static/img/favicon/android-chrome-192x192.png', revision: null },
    { url: '/static/img/favicon/android-chrome-512x512.png', revision: null },
    { url: '/static/img/gifs/offline.gif', revision: null },
    { url: '/static/js/employee_dashboard.js', revision: null },
    { url: '/static/js/manage_employee_details.js', revision: null },
    { url: '/static/js/manual_clocking.js', revision: null },
    { url: '/static/js/shift_logs.js', revision: null },
  ]);

  // For full pages
  workbox.routing.registerRoute(
    ({ request }) => request.mode === 'navigate',
    async ({ event }) => {
      const reqUrl = new URL(event.request.url);
  
      // If request is for the offline page, just serve from cache directly
      if (reqUrl.pathname === '/offline') {
        return caches.match('/offline');
      }
  
      try {
        const preloadResp = await event.preloadResponse;
        if (preloadResp) return preloadResp;
  
        // Include credentials for fetch
        return await fetch(event.request, { credentials: 'include' });
  
      } catch (err) {
        // Offline — redirect to cached offline page with original path encoded
        const redirectUrl = new URL('/offline', self.location.origin);
        redirectUrl.searchParams.set('prev', reqUrl.pathname);
        return Response.redirect(redirectUrl.href, 302);
      }
    }
  );

  // For static requests
  workbox.routing.registerRoute(
    ({ url }) => url.pathname.startsWith('/static/'),
    new workbox.strategies.CacheFirst({
      cacheName: 'static-resources',
      plugins: [
        new workbox.expiration.ExpirationPlugin({ maxEntries: 60, maxAgeSeconds: 7 * 24 * 60 * 60 }),
      ],
    })
  );

  // For API requests
  workbox.routing.registerRoute(
    ({ url }) => url.pathname.startsWith('/api/'),
    async ({ request }) => {
      try {
        const reqWithCreds = new Request(request, { credentials: 'include' });
        return await fetch(reqWithCreds);
      } catch {
        return new Response(JSON.stringify({ Error: 'OFFLINE – request failed.' }), {
          status: 503,
          headers: { 'Content-Type': 'application/json' },
        });
      }
    }
  );

  // Cache manifest but update in the background
  workbox.routing.registerRoute(
    ({ url }) => url.pathname.endsWith('manifest.json'),
    new workbox.strategies.StaleWhileRevalidate({
      cacheName: 'manifest-cache',
    })
  );
}

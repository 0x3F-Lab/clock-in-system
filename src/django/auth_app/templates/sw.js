// Load workbox from CDN
importScripts('https://storage.googleapis.com/workbox-cdn/releases/6.5.4/workbox-sw.js');

// Determine if in dev environment
const isDevEnvironment = self.location.hostname === 'localhost' || self.location.hostname === '127.0.0.1';


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

// Set URLs
const OFFLINE_URL = "{{ OFFLINE_URL|default:'/offline'|escapejs }}";
const STATIC_URL = "{{ STATIC_URL|default:'/static/'|escapejs }}";
const BASE_URL = "{{ BASE_URL|default:'http://localhost'|escapejs }}";


if (isDevEnvironment) {
  console.log('Running in development mode — disabling caching.');

  // Set workbox to only use Network Only
  workbox.routing.setDefaultHandler(new workbox.strategies.NetworkOnly());


} else {
  // Set routes to precache (i.e. static files)
  workbox.precaching.precacheAndRoute([
    { url: OFFLINE_URL, revision: null },
    { url: `${STATIC_URL}css/styles.css`, revision: null },
    { url: `${STATIC_URL}js/global.js`, revision: null },
    { url: `${STATIC_URL}img/logo.png`, revision: null },
    { url: `${STATIC_URL}favicon.ico`, revision: null },
    { url: `${STATIC_URL}img/favicon/favicon-32x32.png`, revision: null },
    { url: `${STATIC_URL}img/favicon/android-chrome-192x192.png`, revision: null },
    { url: `${STATIC_URL}img/favicon/android-chrome-512x512.png`, revision: null },
    { url: `${STATIC_URL}img/gifs/offline.gif`, revision: null },
    { url: `${STATIC_URL}js/employee_dashboard.js`, revision: null },
    { url: `${STATIC_URL}js/manage_employee_details.js`, revision: null },
    { url: `${STATIC_URL}js/manual_clocking.js`, revision: null },
    { url: `${STATIC_URL}js/shift_logs.js`, revision: null },
  ]);

  // For full pages
  workbox.routing.registerRoute(
    ({ request }) => request.mode === 'navigate',
    async ({ event }) => {
      const reqUrl = new URL(event.request.url);
  
      // If request is for the offline page, just serve from cache directly
      if (reqUrl.pathname === OFFLINE_URL) {
        return caches.match(OFFLINE_URL);
      }
  
      try {
        const preloadResp = await event.preloadResponse;
        if (preloadResp) return preloadResp;
  
        // Include credentials for fetch
        return await fetch(event.request, { credentials: 'same-origin' });
  
      } catch (err) {
        // Offline — redirect to cached offline page with original path encoded
        const redirectUrl = new URL(OFFLINE_URL, self.location.origin);
        redirectUrl.searchParams.set('prev', reqUrl.pathname);
        return Response.redirect(redirectUrl.href, 302);
      }
    }
  );

  // For static requests
  workbox.routing.registerRoute(
    ({ url }) => url.pathname.startsWith(STATIC_URL),
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
        const reqWithCreds = new Request(request, { credentials: 'same-origin' });
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

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
  event.waitUntil(
    (async () => {
      const cacheNames = await caches.keys();
      const expectedPrefix = 'clockinapp-{{ STATIC_CACHE_VER|default:"v0"|escapejs }}';

      await Promise.all(
        cacheNames
          .filter((name) => !name.startsWith(expectedPrefix))
          .map((name) => caches.delete(name))
      );
    })()
  );

  self.clients.claim();
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
  {% load static %}
  workbox.precaching.precacheAndRoute([
    { url: "{{ OFFLINE_URL|default:'/offline'|escapejs }}", revision: "{{ STATIC_CACHE_VER|default:'v0'|escapejs }}" },
    { url: "{% static 'css/styles.css' %}", revision: "{{ STATIC_CACHE_VER|default:'v0'|escapejs }}" },
    { url: "{% static 'js/global.js' %}", revision: "{{ STATIC_CACHE_VER|default:'v0'|escapejs }}" },
    { url: "{% static 'img/logo.png' %}", revision: "{{ STATIC_CACHE_VER|default:'v0'|escapejs }}" },
    { url: "{% static 'favicon.ico' %}", revision: "{{ STATIC_CACHE_VER|default:'v0'|escapejs }}" },
    { url: "{% static 'img/favicon/favicon-32x32.png' %}", revision: "{{ STATIC_CACHE_VER|default:'v0'|escapejs }}" },
    { url: "{% static 'img/favicon/android-chrome-192x192.png' %}", revision: "{{ STATIC_CACHE_VER|default:'v0'|escapejs }}" },
    { url: "{% static 'img/favicon/android-chrome-512x512.png' %}", revision: "{{ STATIC_CACHE_VER|default:'v0'|escapejs }}" },
    { url: "{% static 'img/gifs/offline.gif' %}", revision: "{{ STATIC_CACHE_VER|default:'v0'|escapejs }}" },
    { url: "{% static 'js/employee_dashboard.js' %}", revision: "{{ STATIC_CACHE_VER|default:'v0'|escapejs }}" },
    { url: "{% static 'js/employee_account.js' %}", revision: "{{ STATIC_CACHE_VER|default:'v0'|escapejs }}" },
    { url: "{% static 'js/manage_employee_details.js' %}", revision: "{{ STATIC_CACHE_VER|default:'v0'|escapejs }}" },
    { url: "{% static 'js/manual_clocking.js' %}", revision: "{{ STATIC_CACHE_VER|default:'v0'|escapejs }}" },
    { url: "{% static 'js/shift_logs.js' %}", revision: "{{ STATIC_CACHE_VER|default:'v0'|escapejs }}" },
    { url: "{% static 'js/notification_page.js' %}", revision: "{{ STATIC_CACHE_VER|default:'v0'|escapejs }}" },
    { url: "{% static 'js/manage_stores.js' %}", revision: "{{ STATIC_CACHE_VER|default:'v0'|escapejs }}" },
    { url: "{% static 'js/schedule_dashboard.js' %}", revision: "{{ STATIC_CACHE_VER|default:'v0'|escapejs }}" },
    { url: "{% static 'js/exception_page.js' %}", revision: "{{ STATIC_CACHE_VER|default:'v0'|escapejs }}" },
  ]);

  // For full pages
  workbox.routing.registerRoute(
    ({ request }) => request.mode === 'navigate',
    async ({ event }) => {
      const reqUrl = new URL(event.request.url);

      // If already requesting the offline page directly
      if (reqUrl.pathname === OFFLINE_URL) {
        const cachedOffline = await caches.match(OFFLINE_URL);
        if (cachedOffline) {
          return cachedOffline;
        }

        // Fallback if offline page wasn't cached
        return new Response('Offline – page not available. Please fix your connection.', {
          status: 503,
          headers: { 'Content-Type': 'text/plain' },
        });
      }

      // Other resources/pages
      try {
        const preloadResp = await event.preloadResponse;
        if (preloadResp) return preloadResp;

        // Attempt normal fetch with credentials if resource not cached
        return await fetch(event.request, { credentials: 'same-origin' });

      } catch (err) {
        const cachedOffline = await caches.match(OFFLINE_URL);
        if (cachedOffline) {
          const redirectUrl = new URL(OFFLINE_URL, self.location.origin);
          redirectUrl.searchParams.set('prev', reqUrl.pathname);
          return Response.redirect(redirectUrl.href, 302);
        }

        // Fallback if offline page wasn't cached
        return new Response('Offline – page not available. Please fix your connection.', {
          status: 503,
          headers: { 'Content-Type': 'text/plain' },
        });
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

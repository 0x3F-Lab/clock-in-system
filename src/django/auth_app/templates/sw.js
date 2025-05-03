// NOTE: THIS FILE IS PLACED IN TEMPLATES SECTION TO ENSURE IT LOADS ON THE BASE PATH AND GET FULL SCOPE

const CACHE_NAME = 'clockinapp-cache-v1';

const urlsToCache = [
    '/',  // Root URL
    '/offline/',
    '/sw.js',
    '/static/css/styles.css',
    '/static/js/global.js',
    '/static/img/logo.png',
    '/static/favicon.ico',
    '/static/img/favicon/favicon-32x32.png',
    '/static/img/favicon/android-chrome-192x192.png',
    '/static/img/favicon/android-chrome-512x512.png',
    '/static/img/gifs/offline.gif',
    '/static/js/employee_dashboard.js',
    '/static/js/manage_employee_details.js',
    '/static/js/manual_clocking.js',
    '/static/js/shift_logs.js',
];

// Install SW and cache assets
self.addEventListener('install', event => {
  event.waitUntil(
    caches.open(CACHE_NAME).then(cache => {
      return Promise.all(urlsToCache.map(url => {
        return fetch(url)
          .then(response => {
            if (response.ok) {
              return cache.put(url, response);
            } else {
              throw new Error(`Failed to fetch resource '${url}'.`);
            }
          })
          .catch(err => {
            console.error(err);
            return null; // Proceed even if some resources fail to load
          });
      }));
    })
  );
  self.skipWaiting(); // Activate worker
});

// Activate SW and clean up old caches
self.addEventListener('activate', event => {
  event.waitUntil(
    (async () => {
      // Enable navigation preload if supported
      if (self.registration.navigationPreload) {
        await self.registration.navigationPreload.enable();
      }

      const cacheNames = await caches.keys();
      await Promise.all(
        cacheNames.map(name => {
          if (name !== CACHE_NAME) return caches.delete(name);
        })
      );
      self.clients.claim(); // Take control of clients
    })()
  );
});

// Intercept requests and include credentials
self.addEventListener('fetch', event => {
  const { request } = event;

  // Skip caching for external resources with integrity hashes
  if (request.url.includes('cdn.jsdelivr.net') || request.url.includes('code.jquery.com')) {
    // Fetch from the network and bypass cache for external resources
    event.respondWith(fetch(request));
    return;
  }

  // Handle navigation (page loads)
  if (event.request.mode === 'navigate') {
    const reqUrl = new URL(request.url);
    const pathname = reqUrl.pathname;

    // If the user is already going to /offline, just serve it
    if (pathname === '/offline/') {
      event.respondWith(
        caches.match('/offline/')
          .then(cached => cached || fetch(request))
      );
      return;
    }

    // All other navs: try network (with preload) then redirect to offline on failure
    event.respondWith((async () => {
      try {
        const preloadResponse = await event.preloadResponse;
        if (preloadResponse) return preloadResponse;
        return await fetch(request, { credentials: 'include' });
      } catch (err) {
        // Build a URL like `/offline?prev=/your/path`
        const redirectUrl = new URL('/offline/', self.location.origin);
        redirectUrl.searchParams.set('prev', pathname);
        return Response.redirect(redirectUrl.href, 302);
      }
    })());
    return;
  }

  // Handle API calls separately (e.g., /api/)
  if (request.url.includes('/api/')) {
    event.respondWith(
      fetch(request, { credentials: 'include' })
        .catch(() => {
          return new Response(
            JSON.stringify({ Error: 'OFFLINE – request failed.' }),
            {
              status: 503,
              headers: { 'Content-Type': 'application/json' }
            }
          );
          })
    );
    return;
  }

  // Handle static assets (e.g., /static/)
  event.respondWith(
    caches.match(request).then(cachedResponse => {
      if (cachedResponse) return cachedResponse;

      const fetchRequest = new Request(request, {
        credentials: 'include',
        method: request.method,
        headers: request.headers,
        mode: request.mode,
        redirect: request.redirect,
        referrer: request.referrer
      });

      return fetch(fetchRequest).catch(() => {
        // Optionally return fallback assets or just fail silently
        return new Response('', { status: 503 });
      });
    })
  );
});

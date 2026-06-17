// ── Cache version — bump this string to invalidate all caches on next deploy ──
const VERSION = 'v3';

const STATIC_CACHE  = `mdh-static-${VERSION}`;
const DYNAMIC_CACHE = `mdh-dynamic-${VERSION}`;

// Pre-cached shell — versioned, rarely changing assets
const STATIC_ASSETS = [
  '/offline',
  '/static/css/base.css',
  '/static/js/main.js',
  '/static/icons/icon-192.png',
  '/static/icons/icon-512.png',
];

// ── Helpers ────────────────────────────────────────────────────────────────────

function isStaticAsset(url) {
  const p = url.pathname;
  return p.startsWith('/static/') || p === '/offline';
}

function isApiRequest(url) {
  return (
    url.pathname.startsWith('/checkout') ||
    url.pathname.startsWith('/verify-payment') ||
    url.pathname.startsWith('/track') ||
    url.pathname.startsWith('/push/') ||
    url.pathname.startsWith('/admin/') ||
    url.pathname.startsWith('/dashboard/') ||
    url.pathname.startsWith('/auth/')
  );
}

function isNavigationRequest(request) {
  return request.mode === 'navigate';
}

function trimCache(cacheName, maxItems) {
  caches.open(cacheName).then(cache =>
    cache.keys().then(keys => {
      if (keys.length > maxItems) {
        cache.delete(keys[0]).then(() => trimCache(cacheName, maxItems));
      }
    })
  );
}

// ── Install: pre-cache the app shell ──────────────────────────────────────────
self.addEventListener('install', e => {
  e.waitUntil(
    caches.open(STATIC_CACHE)
      .then(c => c.addAll(STATIC_ASSETS))
      .then(() => self.skipWaiting())
  );
});

// ── Activate: purge stale caches ──────────────────────────────────────────────
self.addEventListener('activate', e => {
  const keep = [STATIC_CACHE, DYNAMIC_CACHE];
  e.waitUntil(
    caches.keys()
      .then(keys => Promise.all(
        keys.filter(k => !keep.includes(k)).map(k => caches.delete(k))
      ))
      .then(() => self.clients.claim())
  );
});

// ── Fetch ──────────────────────────────────────────────────────────────────────
self.addEventListener('fetch', e => {
  if (e.request.method !== 'GET') return;

  const url = new URL(e.request.url);

  // Never intercept cross-origin requests (Paystack, Google Fonts, etc.)
  if (url.origin !== self.location.origin) return;

  // Never intercept notification/push poll endpoints
  if (
    url.pathname.startsWith('/push/') ||
    url.pathname.startsWith('/admin/notifications') ||
    url.pathname.startsWith('/dashboard/notifications')
  ) return;

  // API routes — network only, no caching
  if (isApiRequest(url)) {
    e.respondWith(fetch(e.request));
    return;
  }

  // Static assets (CSS, JS, icons, fonts) — cache-first
  if (isStaticAsset(url)) {
    e.respondWith(
      caches.open(STATIC_CACHE).then(cache =>
        cache.match(e.request).then(cached => {
          if (cached) return cached;
          return fetch(e.request).then(resp => {
            cache.put(e.request, resp.clone());
            return resp;
          });
        })
      )
    );
    return;
  }

  // HTML navigation — network-first, fallback to cache, then offline page
  if (isNavigationRequest(e.request)) {
    e.respondWith(
      fetch(e.request)
        .then(resp => {
          const clone = resp.clone();
          caches.open(DYNAMIC_CACHE).then(c => {
            c.put(e.request, clone);
            trimCache(DYNAMIC_CACHE, 20);
          });
          return resp;
        })
        .catch(() =>
          caches.match(e.request)
            .then(cached => cached || caches.match('/offline'))
        )
    );
    return;
  }

  // Everything else — stale-while-revalidate
  e.respondWith(
    caches.open(DYNAMIC_CACHE).then(cache =>
      cache.match(e.request).then(cached => {
        const fetchPromise = fetch(e.request).then(resp => {
          cache.put(e.request, resp.clone());
          trimCache(DYNAMIC_CACHE, 30);
          return resp;
        });
        return cached || fetchPromise;
      })
    )
  );
});

// ── Message: handle SKIP_WAITING from update flow ─────────────────────────────
self.addEventListener('message', e => {
  if (e.data && e.data.type === 'SKIP_WAITING') self.skipWaiting();
});

// ── Push: show notification ────────────────────────────────────────────────────
self.addEventListener('push', e => {
  let data = {
    title: 'Mac Data Hub',
    body:  'You have a new notification.',
    url:   '/',
    icon:  '/static/icons/icon-192.png',
  };
  if (e.data) {
    try { data = { ...data, ...JSON.parse(e.data.text()) }; } catch (_) {}
  }
  e.waitUntil(
    self.registration.showNotification(data.title, {
      body:    data.body,
      icon:    data.icon,
      badge:   '/static/icons/icon-192.png',
      data:    { url: data.url },
      vibrate: [200, 100, 200],
      tag:     'mdh-notification',
      renotify: true,
    })
  );
});

// ── Notification click ─────────────────────────────────────────────────────────
self.addEventListener('notificationclick', e => {
  e.notification.close();
  const target = (e.notification.data && e.notification.data.url) || '/';
  e.waitUntil(
    clients.matchAll({ type: 'window', includeUncontrolled: true }).then(list => {
      for (const client of list) {
        if (client.url === target && 'focus' in client) return client.focus();
      }
      if (clients.openWindow) return clients.openWindow(target);
    })
  );
});

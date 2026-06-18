// ── Cache version — bump this string to invalidate all caches on next deploy ──
const VERSION = 'v4';

const STATIC_CACHE  = `mdh-static-${VERSION}`;
const DYNAMIC_CACHE = `mdh-dynamic-${VERSION}`;

// Pre-cached app shell — everything a reseller/admin needs without hitting the network
const STATIC_ASSETS = [
  '/offline',
  '/static/css/base.css',
  '/static/css/dashboard.css',
  '/static/js/main.js',
  '/static/icons/icon-192.png',
  '/static/icons/icon-512.png',
];

// ── Helpers ────────────────────────────────────────────────────────────────────

// Strip query strings when caching static assets so ?v=123 busting params
// don't create duplicate cache entries for the same file.
function staticCacheKey(request) {
  const url = new URL(request.url);
  url.search = '';
  return new Request(url.toString(), { headers: request.headers });
}

function isStaticAsset(url) {
  const p = url.pathname;
  return p.startsWith('/static/') || p === '/offline';
}

// Routes that must always go to the network — never cache responses here
function isNetworkOnly(url) {
  return (
    url.pathname.startsWith('/push/') ||
    url.pathname.startsWith('/checkout') ||
    url.pathname.startsWith('/verify-payment') ||
    url.pathname.startsWith('/track') ||
    url.pathname.startsWith('/auth/') ||
    url.pathname.startsWith('/admin/') ||
    url.pathname.startsWith('/dashboard/notifications') ||
    url.pathname.startsWith('/webhook/')
  );
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

// ── Activate: purge all stale caches from old versions ────────────────────────
self.addEventListener('activate', e => {
  const keep = new Set([STATIC_CACHE, DYNAMIC_CACHE]);
  e.waitUntil(
    caches.keys()
      .then(keys => Promise.all(keys.filter(k => !keep.has(k)).map(k => caches.delete(k))))
      .then(() => self.clients.claim())
  );
});

// ── Fetch ──────────────────────────────────────────────────────────────────────
self.addEventListener('fetch', e => {
  if (e.request.method !== 'GET') return;

  const url = new URL(e.request.url);

  // Never intercept cross-origin requests (Paystack, Google Fonts, CDNs, etc.)
  if (url.origin !== self.location.origin) return;

  // Network-only routes — no caching, always live
  if (isNetworkOnly(url)) {
    e.respondWith(fetch(e.request));
    return;
  }

  // Static assets — cache-first, update in background if stale
  if (isStaticAsset(url)) {
    const key = staticCacheKey(e.request);
    e.respondWith(
      caches.open(STATIC_CACHE).then(cache =>
        cache.match(key).then(cached => {
          const networkFetch = fetch(e.request).then(resp => {
            if (resp.ok) cache.put(key, resp.clone());
            return resp;
          });
          // Return cache immediately; fetch runs in background to keep it fresh
          return cached || networkFetch;
        })
      )
    );
    return;
  }

  // HTML navigation — network-first, fall back to cache, then offline page
  if (e.request.mode === 'navigate') {
    e.respondWith(
      fetch(e.request)
        .then(resp => {
          const clone = resp.clone();
          caches.open(DYNAMIC_CACHE).then(c => {
            c.put(e.request, clone);
            trimCache(DYNAMIC_CACHE, 25);
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
          if (resp.ok) {
            cache.put(e.request, resp.clone());
            trimCache(DYNAMIC_CACHE, 40);
          }
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
    type:  'order',
  };
  if (e.data) {
    try { data = { ...data, ...JSON.parse(e.data.text()) }; } catch (_) {}
  }

  // Broadcasts get their own tag so they don't replace order notifications
  const tag = data.type === 'broadcast' ? 'mdh-broadcast' : 'mdh-order';

  e.waitUntil(
    self.registration.showNotification(data.title, {
      body:     data.body,
      icon:     data.icon,
      badge:    '/static/icons/icon-192.png',
      data:     { url: data.url },
      vibrate:  [200, 100, 200],
      tag:      tag,
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

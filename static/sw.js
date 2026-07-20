self.addEventListener('install', event => {
  event.waitUntil(
    caches.open('cyber-v1').then(cache => {
      return cache.addAll(['/']); // add more assets later
    })
  );
});

self.addEventListener('fetch', event => {
  event.respondWith(
    caches.match(event.request).then(response => response || fetch(event.request))
  );
});
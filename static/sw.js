// Service Worker for Car Contact Web Push Notifications
self.addEventListener('install', (event) => {
  self.skipWaiting();
});

self.addEventListener('activate', (event) => {
  event.waitUntil(self.clients.claim());
});

self.addEventListener('push', (event) => {
  let data = {
    title: '🚨 Car Alert Received!',
    body: 'Someone scanned your car QR code.',
    url: '/',
    actionType: 'alert'
  };

  try {
    if (event.data) {
      data = Object.assign(data, event.data.json());
    }
  } catch (e) {
    console.error('Error parsing push data:', e);
  }

  const options = {
    body: data.body,
    icon: '/static/icons/car-icon.png',
    badge: '/static/icons/badge.png',
    vibrate: [500, 200, 500, 200, 500, 200, 1000],
    sound: '/static/sounds/alarm.wav',
    silent: false,
    tag: 'car-alert-' + Date.now(),
    renotify: true,
    requireInteraction: true,
    data: {
      url: data.url || '/',
      actionType: data.actionType
    },
    actions: [
      { action: 'open', title: '👀 View Alert' },
      { action: 'dismiss', title: 'Dismiss' }
    ]
  };

  event.waitUntil(
    self.registration.showNotification(data.title, options)
  );
});

self.addEventListener('notificationclick', (event) => {
  event.notification.close();

  if (event.action === 'dismiss') {
    return;
  }

  const targetUrl = event.notification.data?.url || '/';

  event.waitUntil(
    clients.matchAll({ type: 'window', includeUncontrolled: true }).then((clientList) => {
      for (const client of clientList) {
        if (client.url.includes(targetUrl) && 'focus' in client) {
          client.postMessage({ type: 'TRIGGER_SOUND', actionType: event.notification.data?.actionType });
          return client.focus();
        }
      }
      if (clients.openWindow) {
        return clients.openWindow(targetUrl + '?autoring=1');
      }
    })
  );
});

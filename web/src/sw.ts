/// <reference lib="webworker" />
// Service worker: muestra las notificaciones push de Firebase cuando el panel está cerrado
// y guarda la app para abrirla sin señal (vista del guardia).
import { initializeApp } from 'firebase/app'
import { getMessaging } from 'firebase/messaging/sw'

declare const self: ServiceWorkerGlobalScope

const config = new URL(self.location.href).searchParams.get('firebase')
if (config) {
  // Con un mensaje que trae "notification", el SDK la muestra y abre fcm_options.link al tocarla.
  getMessaging(initializeApp(JSON.parse(config)))
}

const CACHE = 'vigilant-v1'

self.addEventListener('install', () => void self.skipWaiting())
self.addEventListener('activate', (e) => e.waitUntil(self.clients.claim()))

// Navegaciones: red primero y, sin señal, la última versión guardada de la app.
// La API (/v1) nunca se guarda en caché.
self.addEventListener('fetch', (e) => {
  const req = e.request
  const url = new URL(req.url)
  if (req.method !== 'GET' || url.origin !== self.location.origin || url.pathname.startsWith('/v1')) return
  if (req.mode === 'navigate') {
    e.respondWith(
      fetch(req)
        .then((r) => {
          const copia = r.clone()
          void caches.open(CACHE).then((c) => c.put('/index.html', copia))
          return r
        })
        .catch(async () => (await caches.match('/index.html')) ?? Response.error()),
    )
    return
  }
  if (url.pathname.startsWith('/assets/')) {
    // Archivos con hash en el nombre: nunca cambian, se pueden servir desde caché.
    e.respondWith(
      caches.match(req).then(
        (hit) =>
          hit ??
          fetch(req).then((r) => {
            const copia = r.clone()
            void caches.open(CACHE).then((c) => c.put(req, copia))
            return r
          }),
      ),
    )
  }
})

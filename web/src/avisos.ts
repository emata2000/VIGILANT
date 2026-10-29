// Notificaciones push en el navegador (administrador y dueño de nave) con Firebase.
import { initializeApp, type FirebaseOptions } from 'firebase/app'
import { getMessaging, getToken, isSupported, onMessage } from 'firebase/messaging'
import { api } from './api'

interface PushConfig {
  habilitado: boolean
  firebase: FirebaseOptions | null
  vapid_key: string | null
}

const LLAVE = 'vigilant.push'

export type EstadoAvisos = 'no-disponible' | 'pendiente' | 'activos' | 'bloqueados'

let config: PushConfig | null = null

async function cargarConfig(): Promise<PushConfig | null> {
  if (!config) config = await api<PushConfig>('/v1/push/config').catch(() => null)
  return config?.habilitado ? config : null
}

export async function estadoAvisos(): Promise<EstadoAvisos> {
  if (!('Notification' in window) || !('serviceWorker' in navigator) || !(await isSupported())) return 'no-disponible'
  if (!(await cargarConfig())) return 'no-disponible'
  if (Notification.permission === 'denied') return 'bloqueados'
  return Notification.permission === 'granted' ? 'activos' : 'pendiente'
}

async function registrarSw(cfg: PushConfig) {
  const archivo = import.meta.env.DEV ? '/src/sw.ts' : '/sw.js'
  const url = `${archivo}?firebase=${encodeURIComponent(JSON.stringify(cfg.firebase))}`
  return navigator.serviceWorker.register(url, { type: 'module' })
}

/** Pide permiso (si hace falta), obtiene el token y lo registra en la API. */
export async function activarAvisos(usuarioId: number): Promise<boolean> {
  const cfg = await cargarConfig()
  if (!cfg?.firebase || !cfg.vapid_key) return false
  if (Notification.permission !== 'granted' && (await Notification.requestPermission()) !== 'granted') return false
  const registro = await registrarSw(cfg)
  await navigator.serviceWorker.ready
  const messaging = getMessaging(initializeApp(cfg.firebase))
  const token = await getToken(messaging, { vapidKey: cfg.vapid_key, serviceWorkerRegistration: registro })
  const clave = `${usuarioId}:${token}`
  let previo: string | null = null
  try {
    previo = localStorage.getItem(LLAVE)
  } catch {
    /* sin almacenamiento */
  }
  if (previo !== clave) {
    await api('/v1/dispositivos', { cuerpo: { fcm_token: token, plataforma: 'web' } })
    try {
      localStorage.setItem(LLAVE, clave)
    } catch {
      /* sin almacenamiento */
    }
  }
  // Con el panel abierto el SDK no muestra la notificación: se muestra aquí.
  onMessage(messaging, (m) => {
    void registro.showNotification(m.notification?.title ?? 'VIGILANT', {
      body: m.notification?.body,
      icon: '/icono-192.png',
      data: { url: '/bitacora' },
    })
  })
  return true
}

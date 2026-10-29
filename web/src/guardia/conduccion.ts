// Modo conducción del PRD, en versión navegador:
// - arriba de 10 km/h la pantalla se bloquea para que el guardia no escriba manejando;
// - se desbloquea tras 3 s detenido;
// - al acercarse a 25 m de un punto de control, lo anuncia por voz;
// - la pantalla no se apaga mientras la vista está abierta.
import { useEffect, useRef, useState } from 'react'
import type { PuntoControl } from '../api'

const BLOQUEO_KMH = 10
const DETENIDO_KMH = 2
const DETENIDO_MS = 3000
const RADIO_AVISO_M = 25
const REPETIR_AVISO_MS = 10 * 60 * 1000

export function distanciaM(a: { lat: number; lng: number }, b: { lat: number; lng: number }): number {
  const R = 6371000
  const rad = Math.PI / 180
  const dLat = (b.lat - a.lat) * rad
  const dLng = (b.lng - a.lng) * rad
  const h = Math.sin(dLat / 2) ** 2 + Math.cos(a.lat * rad) * Math.cos(b.lat * rad) * Math.sin(dLng / 2) ** 2
  return 2 * R * Math.asin(Math.sqrt(h))
}

function hablar(texto: string) {
  if (!('speechSynthesis' in window)) return
  const u = new SpeechSynthesisUtterance(texto)
  u.lang = 'es-MX'
  u.rate = 1
  u.volume = 1
  speechSynthesis.cancel()
  speechSynthesis.speak(u)
}

export function useConduccion(puntos: PuntoControl[]) {
  const [velocidadKmh, setVelocidad] = useState(0)
  const [bloqueado, setBloqueado] = useState(false)
  const puntosRef = useRef(puntos)
  puntosRef.current = puntos

  useEffect(() => {
    if (!navigator.geolocation) return
    let anterior: GeolocationPosition | null = null
    let detenidoDesde: number | null = null
    let bloqueadoAhora = false
    let ultimaLectura = 0
    const avisados = new Map<number, number>()

    const id = navigator.geolocation.watchPosition(
      (pos) => {
        const { latitude: lat, longitude: lng, speed, accuracy } = pos.coords
        let kmh = speed != null && speed >= 0 ? speed * 3.6 : null
        if (kmh == null && anterior) {
          // Sin velocidad del GPS: se estima con la posición anterior, ignorando el ruido.
          const d = distanciaM({ lat, lng }, { lat: anterior.coords.latitude, lng: anterior.coords.longitude })
          const s = (pos.timestamp - anterior.timestamp) / 1000
          kmh = s > 0 && d > Math.max(accuracy, 5) ? (d / s) * 3.6 : 0
        }
        anterior = pos
        ultimaLectura = Date.now()
        kmh = kmh ?? 0
        setVelocidad(kmh)

        if (kmh > BLOQUEO_KMH) {
          bloqueadoAhora = true
          detenidoDesde = null
        } else if (bloqueadoAhora && kmh < DETENIDO_KMH) {
          detenidoDesde ??= pos.timestamp
          if (pos.timestamp - detenidoDesde >= DETENIDO_MS) bloqueadoAhora = false
        } else {
          detenidoDesde = null
        }
        setBloqueado(bloqueadoAhora)

        const ahora = Date.now()
        for (const p of puntosRef.current) {
          if (distanciaM({ lat, lng }, p.coordenada_esperada) > RADIO_AVISO_M) continue
          if (ahora - (avisados.get(p.id) ?? 0) < REPETIR_AVISO_MS) continue
          avisados.set(p.id, ahora)
          hablar(`Aproximándose a ${p.nombre_punto}. Detenga el vehículo para iniciar la inspección.`)
          break
        }
      },
      () => {},
      { enableHighAccuracy: true, maximumAge: 1000 },
    )
    // Algunos teléfonos dejan de mandar posiciones cuando no hay movimiento:
    // sin lecturas nuevas en 5 s se considera detenido.
    const revision = setInterval(() => {
      if (bloqueadoAhora && Date.now() - ultimaLectura > DETENIDO_MS + 2000) {
        bloqueadoAhora = false
        detenidoDesde = null
        setBloqueado(false)
        setVelocidad(0)
      }
    }, 1000)
    return () => {
      navigator.geolocation.clearWatch(id)
      clearInterval(revision)
    }
  }, [])

  // Mantener la pantalla encendida (teléfono en el soporte del manubrio).
  useEffect(() => {
    let candado: WakeLockSentinel | null = null
    const pedir = () => {
      if (document.visibilityState === 'visible' && 'wakeLock' in navigator)
        navigator.wakeLock
          .request('screen')
          .then((c) => (candado = c))
          .catch(() => {})
    }
    pedir()
    document.addEventListener('visibilitychange', pedir)
    return () => {
      document.removeEventListener('visibilitychange', pedir)
      void candado?.release()
    }
  }, [])

  return { velocidadKmh, bloqueado }
}

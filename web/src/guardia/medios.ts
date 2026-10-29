export interface Posicion {
  lat: number
  lng: number
  precision_metros: number
}

/** Posición actual del GPS, o null si no hay permiso o señal en `msMax`. */
export function obtenerPosicion(msMax = 15_000): Promise<Posicion | null> {
  return new Promise((ok) => {
    if (!navigator.geolocation) return ok(null)
    navigator.geolocation.getCurrentPosition(
      (p) => ok({ lat: p.coords.latitude, lng: p.coords.longitude, precision_metros: p.coords.accuracy }),
      () => ok(null),
      { enableHighAccuracy: true, timeout: msMax, maximumAge: 10_000 },
    )
  })
}

/** Reduce la foto a 1600 px y JPEG para que suba rápido con poca señal. */
export async function comprimirFoto(archivo: File, ladoMax = 1600): Promise<Blob> {
  try {
    const img = await createImageBitmap(archivo, { imageOrientation: 'from-image' })
    const escala = Math.min(1, ladoMax / Math.max(img.width, img.height))
    const c = document.createElement('canvas')
    c.width = Math.round(img.width * escala)
    c.height = Math.round(img.height * escala)
    c.getContext('2d')!.drawImage(img, 0, 0, c.width, c.height)
    return await new Promise<Blob>((ok, mal) => c.toBlob((b) => (b ? ok(b) : mal()), 'image/jpeg', 0.8))
  } catch {
    return archivo
  }
}

// Reportes que no se pudieron enviar (sin señal). Se guardan en IndexedDB con su foto
// y se reintentan al recuperar conexión. El uuid_cliente evita duplicados en el servidor.
import { createStore, del, entries, set } from 'idb-keyval'
import { api, ErrorApi, subirFoto, type Reporte, type ReporteIn } from '../api'

export interface Pendiente {
  reporte: ReporteIn
  foto: Blob | null
  error?: string
}

const almacen = createStore('vigilant', 'pendientes')

export async function encolar(p: Pendiente) {
  await set(p.reporte.uuid_cliente, p, almacen)
}

export async function pendientes(): Promise<Pendiente[]> {
  try {
    return (await entries<string, Pendiente>(almacen)).map(([, v]) => v)
  } catch {
    return []
  }
}

export async function descartar(uuid: string) {
  await del(uuid, almacen)
}

/** ¿El fallo fue de red o del servidor (vale la pena reintentar)? */
export function esFalloTemporal(e: unknown) {
  return !(e instanceof ErrorApi) || e.status >= 500 || e.status === 408 || e.status === 429
}

/** Sube la foto (si hay) y envía el reporte. */
export async function enviar(p: Pendiente): Promise<Reporte> {
  const reporte = { ...p.reporte }
  if (p.foto) reporte.multimedia = [{ storage_key: await subirFoto(p.foto), tipo: 'foto' }]
  return api<Reporte>('/v1/reportes', { cuerpo: reporte })
}

let sincronizando = false

/** Intenta enviar todo lo pendiente. Devuelve cuántos se enviaron. */
export async function sincronizar(): Promise<number> {
  if (sincronizando || !navigator.onLine) return 0
  sincronizando = true
  let enviados = 0
  try {
    const lista = (await pendientes()).sort((a, b) => a.reporte.timestamp_campo.localeCompare(b.reporte.timestamp_campo))
    for (const p of lista) {
      if (p.error) continue // rechazado por el servidor: el guardia decide
      try {
        await enviar(p)
        await descartar(p.reporte.uuid_cliente)
        enviados++
      } catch (e) {
        if (esFalloTemporal(e)) break
        await encolar({ ...p, error: (e as Error).message })
      }
    }
  } finally {
    sincronizando = false
  }
  return enviados
}

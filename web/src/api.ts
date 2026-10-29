// Cliente de la API de VIGILANT. Los tipos reflejan backend/app/schemas.py.

export type Rol = 'SUPER_ADMIN' | 'ADMINISTRADOR' | 'DUENO_NAVE' | 'GUARDIA'
export type TipoEvento = 'RUTINA_PASO' | 'ALERTA_EMERGENCIA'

export interface Sesion {
  access_token: string
  usuario_id: number
  tenant_id: number | null
  rol: Rol
  zona_horaria: string | null
  empresa: string | null
}

export interface Usuario {
  id: number
  tenant_id: number | null
  email: string
  nombre: string
  telefono_whatsapp: string | null
  rol: Rol
  status: string
}

export interface Tenant {
  id: number
  slug: string
  nombre_comercial: string
  zona_horaria: string
  status: 'active' | 'suspended' | 'trial'
  token_identificador: string
}

/** Polígono GeoJSON: coordenadas [lng, lat]. */
export interface Poligono {
  type: 'Polygon'
  coordinates: [number, number][][]
}

export interface Geocerca {
  id: number
  tenant_id: number
  nombre_bodega: string
  num_bodega: string | null
  cliente_id: number | null
  perimetro: Poligono
}

export interface Coordenada {
  lat: number
  lng: number
}

export interface PuntoControl {
  id: number
  codigo_uid: string
  nombre_punto: string
  bodega_id: number | null
  coordenada_esperada: Coordenada
  tolerancia_metros: number
}

export interface ReporteIn {
  uuid_cliente: string
  tipo_evento: TipoEvento
  timestamp_campo: string
  ubicacion: (Coordenada & { precision_metros?: number | null }) | null
  descripcion?: string | null
  codigo_punto_control?: string | null
  multimedia?: { storage_key: string; tipo: 'foto' }[]
}

export interface Reporte {
  id: number
  uuid_cliente: string
  tipo_evento: TipoEvento
  timestamp_campo: string
  recibido_el: string
  guardia_id: number | null
  guardia_nombre: string | null
  ubicacion: Coordenada | null
  precision_metros: number | null
  bodega_detectada_id: number | null
  punto_control_id: number | null
  estado_notificacion: string
  descripcion: string | null
  multimedia: { tipo: string; url: string }[]
  duplicado: boolean
}

export interface ConfigAlertas {
  recibir_rutina_whatsapp: boolean
  recibir_rutina_push: boolean
  recibir_emergencia_whatsapp: boolean
  recibir_emergencia_push: boolean
  modo_mute_activo: boolean
  mute_inicio_hora: string
  mute_fin_hora: string
}

const BASE = (import.meta.env.VITE_API_URL ?? '').replace(/\/$/, '')
const LLAVE_SESION = 'vigilant.sesion'

export class ErrorApi extends Error {
  status: number
  constructor(status: number, mensaje: string) {
    super(mensaje)
    this.status = status
  }
}

export function leerSesion(): Sesion | null {
  try {
    const s = localStorage.getItem(LLAVE_SESION)
    return s ? (JSON.parse(s) as Sesion) : null
  } catch {
    return null
  }
}

export function guardarSesion(s: Sesion | null) {
  try {
    if (s) localStorage.setItem(LLAVE_SESION, JSON.stringify(s))
    else localStorage.removeItem(LLAVE_SESION)
  } catch {
    /* modo privado: la sesión solo vive en memoria */
  }
}

let alExpirar: () => void = () => {}
export function registrarAlExpirar(fn: () => void) {
  alExpirar = fn
}

function mensajeDeError(cuerpo: unknown, status: number): string {
  const detalle = (cuerpo as { detail?: unknown })?.detail
  if (typeof detalle === 'string') return detalle
  if (Array.isArray(detalle) && detalle.length) {
    // Errores de validación de FastAPI
    return detalle
      .map((d: { loc?: (string | number)[]; msg?: string }) => {
        const campo = d.loc?.slice(1).join('.')
        return campo ? `${campo}: ${d.msg}` : d.msg
      })
      .join('; ')
  }
  return `Error ${status}`
}

export async function api<T>(ruta: string, opciones: { metodo?: string; cuerpo?: unknown } = {}): Promise<T> {
  const sesion = leerSesion()
  const headers: Record<string, string> = {}
  if (opciones.cuerpo !== undefined) headers['Content-Type'] = 'application/json'
  if (sesion) headers.Authorization = `Bearer ${sesion.access_token}`
  const r = await fetch(`${BASE}${ruta}`, {
    method: opciones.metodo ?? (opciones.cuerpo !== undefined ? 'POST' : 'GET'),
    headers,
    body: opciones.cuerpo !== undefined ? JSON.stringify(opciones.cuerpo) : undefined,
  })
  if (r.status === 204) return undefined as T
  const cuerpo = await r.json().catch(() => null)
  if (!r.ok) {
    if (r.status === 401 && sesion && !ruta.startsWith('/v1/auth/login')) alExpirar()
    throw new ErrorApi(r.status, mensajeDeError(cuerpo, r.status))
  }
  return cuerpo as T
}

export async function iniciarSesion(empresa: string, email: string, password: string): Promise<Sesion> {
  const r = await api<Omit<Sesion, 'empresa'>>('/v1/auth/login', {
    cuerpo: { tenant: empresa.trim() || null, email: email.trim(), password },
  })
  const s: Sesion = { ...r, empresa: empresa.trim() || null }
  guardarSesion(s)
  return s
}

/** Sube una foto con URL prefirmada y devuelve su storage_key. */
export async function subirFoto(foto: Blob): Promise<string> {
  const tipo = foto.type || 'image/jpeg'
  const { storage_key, url } = await api<{ storage_key: string; url: string }>('/v1/multimedia/url', {
    cuerpo: { content_type: tipo },
  })
  const r = await fetch(url, { method: 'PUT', headers: { 'Content-Type': tipo }, body: foto })
  if (!r.ok) throw new ErrorApi(r.status, 'No se pudo subir la foto')
  return storage_key
}

export const NOMBRE_ROL: Record<Rol, string> = {
  SUPER_ADMIN: 'Super admin',
  ADMINISTRADOR: 'Administrador',
  DUENO_NAVE: 'Dueño de nave',
  GUARDIA: 'Guardia',
}

export const NOMBRE_ESTADO: Record<string, string> = {
  PENDIENTE: 'Pendiente',
  ENVIADO: 'Notificado',
  SILENCIADO: 'Silenciado',
  TARDIO: 'Llegó tarde',
  SIN_DESTINATARIO: 'Sin destinatario',
}

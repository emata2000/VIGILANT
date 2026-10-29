import { useCallback, useEffect, useRef, useState, type FormEvent } from 'react'
import { api, type PuntoControl, type Reporte, type TipoEvento } from '../api'
import { fechaHora } from '../fechas'
import { useSesion } from '../sesion'
import { descartar, encolar, enviar, esFalloTemporal, pendientes, sincronizar, type Pendiente } from './cola'
import { EscanerQr } from './EscanerQr'
import { comprimirFoto, obtenerPosicion, type Posicion } from './medios'

const LLAVE_PUNTOS = 'vigilant.puntos'

interface Borrador {
  tipo: TipoEvento
  codigo: string | null
  descripcion: string
  foto: Blob | null
  fotoUrl: string | null
}

type EstadoGps = { tipo: 'buscando' } | { tipo: 'ok'; pos: Posicion } | { tipo: 'sin' }

/** Puntos de control guardados para validar el QR aunque no haya señal. */
function puntosGuardados(): PuntoControl[] {
  try {
    return JSON.parse(localStorage.getItem(LLAVE_PUNTOS) ?? '[]') as PuntoControl[]
  } catch {
    return []
  }
}

export function Guardia() {
  const { sesion, salir } = useSesion()
  const [puntos, setPuntos] = useState<PuntoControl[]>(puntosGuardados)
  const [recientes, setRecientes] = useState<Reporte[]>([])
  const [cola, setCola] = useState<Pendiente[]>([])
  const [enLinea, setEnLinea] = useState(navigator.onLine)
  const [escaneando, setEscaneando] = useState(false)
  const [borrador, setBorrador] = useState<Borrador | null>(null)
  const [aviso, setAviso] = useState<{ texto: string; tipo: 'ok' | 'error' | 'info' } | null>(null)

  const refrescar = useCallback(async () => {
    setCola(await pendientes())
    if (!navigator.onLine) return
    try {
      setRecientes(await api<Reporte[]>('/v1/reportes?limite=15'))
    } catch {
      /* sin señal: se queda la lista anterior */
    }
  }, [])

  // Al iniciar turno: bajar puntos de control y sincronizar lo pendiente.
  useEffect(() => {
    api<PuntoControl[]>('/v1/puntos-control')
      .then((p) => {
        setPuntos(p)
        try {
          localStorage.setItem(LLAVE_PUNTOS, JSON.stringify(p))
        } catch {
          /* sin almacenamiento */
        }
      })
      .catch(() => {})
    const sync = async () => {
      const n = await sincronizar()
      if (n) setAviso({ texto: `Se enviaron ${n} reporte(s) guardados sin señal`, tipo: 'ok' })
      await refrescar()
    }
    void sync()
    const enLineaFn = () => {
      setEnLinea(true)
      void sync()
    }
    const fueraFn = () => setEnLinea(false)
    window.addEventListener('online', enLineaFn)
    window.addEventListener('offline', fueraFn)
    const t = setInterval(() => void sync(), 60_000)
    return () => {
      window.removeEventListener('online', enLineaFn)
      window.removeEventListener('offline', fueraFn)
      clearInterval(t)
    }
  }, [refrescar])

  useEffect(() => {
    if (!aviso) return
    const t = setTimeout(() => setAviso(null), 6000)
    return () => clearTimeout(t)
  }, [aviso])

  const alEscanear = useCallback(
    (codigo: string) => {
      setEscaneando(false)
      const punto = puntos.find((p) => p.codigo_uid === codigo)
      if (!punto && puntos.length) {
        setAviso({ texto: `El código “${codigo}” no es un punto de control de tu empresa`, tipo: 'error' })
        return
      }
      setBorrador({ tipo: 'RUTINA_PASO', codigo, descripcion: '', foto: null, fotoUrl: null })
    },
    [puntos],
  )

  const nombrePunto = (codigo: string | null) => puntos.find((p) => p.codigo_uid === codigo)?.nombre_punto

  return (
    <div className="guardia">
      <header className="guardia-cab">
        <div>
          <strong>VIGILANT</strong>
          <span className={`punto-red ${enLinea ? 'en-linea' : ''}`}>{enLinea ? 'En línea' : 'Sin señal'}</span>
        </div>
        <button className="btn-texto claro" onClick={salir}>
          Salir
        </button>
      </header>

      {aviso && <div className={`aviso aviso-${aviso.tipo}`}>{aviso.texto}</div>}

      <main className="guardia-cuerpo">
        <button className="boton-emergencia" onClick={() => setBorrador({ tipo: 'ALERTA_EMERGENCIA', codigo: null, descripcion: '', foto: null, fotoUrl: null })}>
          EMERGENCIA
        </button>
        <div className="botones-guardia">
          <button className="boton-accion" onClick={() => setEscaneando(true)}>
            <span className="icono">▣</span>
            Escanear punto
          </button>
          <button className="boton-accion" onClick={() => setBorrador({ tipo: 'RUTINA_PASO', codigo: null, descripcion: '', foto: null, fotoUrl: null })}>
            <span className="icono">✓</span>
            Rondín sin código
          </button>
        </div>

        {cola.length > 0 && (
          <section className="seccion-guardia">
            <h2>Por enviar ({cola.length})</h2>
            <ul className="lista-guardia">
              {cola.map((p) => (
                <li key={p.reporte.uuid_cliente} className={p.error ? 'con-error' : ''}>
                  <span>
                    {p.reporte.tipo_evento === 'ALERTA_EMERGENCIA' ? 'Emergencia' : 'Rondín'} ·{' '}
                    {fechaHora(p.reporte.timestamp_campo, sesion?.zona_horaria)}
                  </span>
                  {p.error ? (
                    <span className="pequeno">
                      Rechazado: {p.error}{' '}
                      <button
                        className="btn-texto"
                        onClick={async () => {
                          await descartar(p.reporte.uuid_cliente)
                          await refrescar()
                        }}
                      >
                        Descartar
                      </button>
                    </span>
                  ) : (
                    <span className="pequeno tenue">Se enviará al haber señal</span>
                  )}
                </li>
              ))}
            </ul>
          </section>
        )}

        <section className="seccion-guardia">
          <h2>Mis últimos reportes</h2>
          <ul className="lista-guardia">
            {recientes.map((r) => (
              <li key={r.id}>
                <span>
                  {r.tipo_evento === 'ALERTA_EMERGENCIA' ? '🚨 Emergencia' : '✓ Rondín'} ·{' '}
                  {fechaHora(r.timestamp_campo, sesion?.zona_horaria)}
                </span>
                {r.descripcion && <span className="pequeno tenue">{r.descripcion}</span>}
              </li>
            ))}
            {recientes.length === 0 && <li className="tenue">Aún no hay reportes en este turno.</li>}
          </ul>
        </section>
      </main>

      {escaneando && <EscanerQr onCodigo={alEscanear} onCerrar={() => setEscaneando(false)} />}
      {borrador && (
        <FormReporte
          inicial={borrador}
          nombrePunto={nombrePunto(borrador.codigo)}
          onCerrar={() => setBorrador(null)}
          onListo={async (texto, tipo) => {
            setBorrador(null)
            setAviso({ texto, tipo })
            await refrescar()
          }}
        />
      )}
    </div>
  )
}

function FormReporte({
  inicial,
  nombrePunto,
  onCerrar,
  onListo,
}: {
  inicial: Borrador
  nombrePunto?: string
  onCerrar: () => void
  onListo: (texto: string, tipo: 'ok' | 'error' | 'info') => void
}) {
  const [b, setB] = useState(inicial)
  const [gps, setGps] = useState<EstadoGps>({ tipo: 'buscando' })
  const [enviando, setEnviando] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const campoFoto = useRef<HTMLInputElement>(null)
  const emergencia = b.tipo === 'ALERTA_EMERGENCIA'
  // La hora del evento es cuando el guardia abrió el formulario, no cuando llegó la señal.
  const [momento] = useState(() => new Date().toISOString())

  const buscarGps = useCallback(() => {
    setGps({ tipo: 'buscando' })
    void obtenerPosicion().then((pos) => setGps(pos ? { tipo: 'ok', pos } : { tipo: 'sin' }))
  }, [])
  useEffect(buscarGps, [buscarGps])
  useEffect(() => () => void (b.fotoUrl && URL.revokeObjectURL(b.fotoUrl)), [b.fotoUrl])

  async function elegirFoto(archivo: File | undefined) {
    if (!archivo) return
    const foto = await comprimirFoto(archivo)
    setB({ ...b, foto, fotoUrl: URL.createObjectURL(foto) })
  }

  async function mandar(e?: FormEvent) {
    e?.preventDefault()
    setEnviando(true)
    setError(null)
    // Si el GPS sigue buscando, espera un poco más; una emergencia no espera de más.
    let pos = gps.tipo === 'ok' ? gps.pos : null
    if (gps.tipo === 'buscando') pos = await obtenerPosicion(emergencia ? 4000 : 8000)
    const p: Pendiente = {
      reporte: {
        uuid_cliente: crypto.randomUUID(),
        tipo_evento: b.tipo,
        timestamp_campo: momento,
        ubicacion: pos,
        descripcion: b.descripcion.trim() || null,
        codigo_punto_control: b.codigo,
      },
      foto: b.foto,
    }
    try {
      if (!navigator.onLine) throw new TypeError('sin red')
      await enviar(p)
      onListo(emergencia ? 'Emergencia enviada. Se avisó a los responsables.' : 'Rondín registrado', 'ok')
    } catch (err) {
      if (esFalloTemporal(err)) {
        await encolar(p)
        onListo('Sin señal: el reporte se guardó y se enviará solo al recuperar conexión', 'info')
      } else {
        setError((err as Error).message)
        setEnviando(false)
      }
    }
  }

  return (
    <div className="hoja">
      <form className={`hoja-cuerpo ${emergencia ? 'hoja-emergencia' : ''}`} onSubmit={mandar}>
        <div className="hoja-cab">
          <h2>{emergencia ? 'Reportar emergencia' : 'Registrar rondín'}</h2>
          <button type="button" className="btn-texto" onClick={onCerrar} aria-label="Cerrar">
            ✕
          </button>
        </div>

        {b.codigo && (
          <div className="dato">
            <span className="tenue">Punto</span>
            <strong>{nombrePunto ?? b.codigo}</strong>
          </div>
        )}
        <div className="dato">
          <span className="tenue">Ubicación</span>
          {gps.tipo === 'buscando' && <span>Buscando GPS…</span>}
          {gps.tipo === 'ok' && <span className="ok">Lista (±{Math.round(gps.pos.precision_metros)} m)</span>}
          {gps.tipo === 'sin' && (
            <span>
              Sin GPS{' '}
              <button type="button" className="btn-texto" onClick={buscarGps}>
                Reintentar
              </button>
            </span>
          )}
        </div>

        <input
          ref={campoFoto}
          type="file"
          accept="image/*"
          capture="environment"
          hidden
          onChange={(e) => void elegirFoto(e.target.files?.[0])}
        />
        {b.fotoUrl ? (
          <div className="foto-previa">
            <img src={b.fotoUrl} alt="Foto del reporte" />
            <button type="button" className="btn" onClick={() => setB({ ...b, foto: null, fotoUrl: null })}>
              Quitar foto
            </button>
          </div>
        ) : (
          <button type="button" className="btn grande" onClick={() => campoFoto.current?.click()}>
            📷 Tomar foto
          </button>
        )}

        <textarea
          rows={3}
          placeholder={emergencia ? '¿Qué está pasando?' : 'Novedades (opcional)'}
          value={b.descripcion}
          onChange={(e) => setB({ ...b, descripcion: e.target.value })}
          maxLength={4000}
        />
        {error && <p className="error">{error}</p>}
        <button className={`btn grande ${emergencia ? 'peligro' : 'primario'}`} disabled={enviando}>
          {enviando ? 'Enviando…' : emergencia ? 'Enviar emergencia' : 'Enviar rondín'}
        </button>
      </form>
    </div>
  )
}

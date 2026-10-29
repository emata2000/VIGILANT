import { useEffect, useState } from 'react'
import { CircleMarker, Polygon, Popup } from 'react-leaflet'
import { api, NOMBRE_ESTADO, type Geocerca, type Reporte, type TipoEvento } from '../api'
import { anilloAVertices, Mapa, type LatLng } from '../componentes/Mapa'
import { fechaHora, hoyISO } from '../fechas'
import { useSesion } from '../sesion'
import { useCarga } from '../useCarga'

function haceDias(n: number) {
  const d = new Date()
  d.setDate(d.getDate() - n)
  d.setMinutes(d.getMinutes() - d.getTimezoneOffset())
  return d.toISOString().slice(0, 10)
}

export function Bitacora() {
  const { sesion } = useSesion()
  const zona = sesion?.zona_horaria
  const [desde, setDesde] = useState(haceDias(1))
  const [hasta, setHasta] = useState(hoyISO())
  const [nave, setNave] = useState('')
  const [tipo, setTipo] = useState<TipoEvento | ''>('')
  const [vista, setVista] = useState<'lista' | 'mapa'>('lista')
  const [foto, setFoto] = useState<string | null>(null)

  const naves = useCarga(() => api<Geocerca[]>('/v1/geocercas'))
  const reportes = useCarga(() => {
    const q = new URLSearchParams({ limite: '500' })
    // Fechas locales del navegador → instantes ISO con zona.
    if (desde) q.set('desde', new Date(`${desde}T00:00:00`).toISOString())
    if (hasta) {
      const fin = new Date(`${hasta}T00:00:00`)
      fin.setDate(fin.getDate() + 1)
      q.set('hasta', fin.toISOString())
    }
    if (nave) q.set('bodega_id', nave)
    if (tipo) q.set('tipo_evento', tipo)
    return api<Reporte[]>(`/v1/reportes?${q}`)
  }, [desde, hasta, nave, tipo])

  // Refresco automático cada 30 s para ver rondines nuevos.
  const { recargar } = reportes
  useEffect(() => {
    const t = setInterval(() => void recargar(), 30_000)
    return () => clearInterval(t)
  }, [recargar])

  const nombreNave = (id: number | null) =>
    id ? (naves.datos?.find((n) => n.id === id)?.nombre_bodega ?? `Nave #${id}`) : 'Área común'
  const lista = reportes.datos ?? []
  const emergencias = lista.filter((r) => r.tipo_evento === 'ALERTA_EMERGENCIA').length
  const conUbicacion = lista.filter((r) => r.ubicacion)

  return (
    <>
      <div className="cabecera">
        <h1>Bitácora</h1>
        <div className="pestanas compacta">
          <button className={vista === 'lista' ? 'activa' : ''} onClick={() => setVista('lista')}>
            Lista
          </button>
          <button className={vista === 'mapa' ? 'activa' : ''} onClick={() => setVista('mapa')}>
            Mapa
          </button>
        </div>
      </div>
      <div className="filtros">
        <label>
          Desde
          <input type="date" value={desde} onChange={(e) => setDesde(e.target.value)} />
        </label>
        <label>
          Hasta
          <input type="date" value={hasta} onChange={(e) => setHasta(e.target.value)} />
        </label>
        <label>
          Nave
          <select value={nave} onChange={(e) => setNave(e.target.value)}>
            <option value="">Todas</option>
            {naves.datos?.map((n) => (
              <option key={n.id} value={n.id}>
                {n.nombre_bodega}
              </option>
            ))}
          </select>
        </label>
        <label>
          Tipo
          <select value={tipo} onChange={(e) => setTipo(e.target.value as TipoEvento | '')}>
            <option value="">Todos</option>
            <option value="RUTINA_PASO">Rondín</option>
            <option value="ALERTA_EMERGENCIA">Emergencia</option>
          </select>
        </label>
      </div>
      <div className="resumen">
        <div>
          <strong>{lista.length}</strong> reportes
        </div>
        <div className={emergencias ? 'rojo' : ''}>
          <strong>{emergencias}</strong> emergencias
        </div>
      </div>
      {reportes.error && <p className="error">{reportes.error}</p>}

      {vista === 'mapa' ? (
        <Mapa
          alto={520}
          encuadre={[
            ...conUbicacion.map((r) => [r.ubicacion!.lat, r.ubicacion!.lng] as LatLng),
            ...(naves.datos ?? []).flatMap((g) => anilloAVertices(g.perimetro.coordinates[0])),
          ]}
        >
          {naves.datos?.map((g) => (
            <Polygon key={g.id} positions={anilloAVertices(g.perimetro.coordinates[0])} pathOptions={{ color: '#3b82f6', weight: 2 }} />
          ))}
          {conUbicacion.map((r) => (
            <CircleMarker
              key={r.id}
              center={[r.ubicacion!.lat, r.ubicacion!.lng]}
              radius={r.tipo_evento === 'ALERTA_EMERGENCIA' ? 9 : 6}
              pathOptions={{
                color: '#fff',
                weight: 1,
                fillOpacity: 0.9,
                fillColor: r.tipo_evento === 'ALERTA_EMERGENCIA' ? '#dc2626' : '#22c55e',
              }}
            >
              <Popup>
                <strong>{r.tipo_evento === 'ALERTA_EMERGENCIA' ? 'Emergencia' : 'Rondín'}</strong>
                <br />
                {fechaHora(r.timestamp_campo, zona)} · {r.guardia_nombre ?? 'Guardia'}
                <br />
                {nombreNave(r.bodega_detectada_id)}
                {r.descripcion && (
                  <>
                    <br />
                    {r.descripcion}
                  </>
                )}
              </Popup>
            </CircleMarker>
          ))}
        </Mapa>
      ) : (
        <ul className="eventos">
          {lista.map((r) => (
            <li key={r.id} className={r.tipo_evento === 'ALERTA_EMERGENCIA' ? 'emergencia' : ''}>
              <div className="evento-cab">
                <span className={`chip ${r.tipo_evento === 'ALERTA_EMERGENCIA' ? 'chip-rojo' : 'chip-verde'}`}>
                  {r.tipo_evento === 'ALERTA_EMERGENCIA' ? 'Emergencia' : 'Rondín'}
                </span>
                <span className="hora">{fechaHora(r.timestamp_campo, zona)}</span>
              </div>
              <div className="evento-cuerpo">
                <div>
                  <strong>{nombreNave(r.bodega_detectada_id)}</strong>
                  <span className="tenue"> · {r.guardia_nombre ?? 'Guardia'}</span>
                  {r.punto_control_id && <span className="tenue"> · punto escaneado</span>}
                  {!r.ubicacion && <span className="tenue"> · sin GPS</span>}
                </div>
                {r.descripcion && <p>{r.descripcion}</p>}
                <div className="tenue pequeno">Aviso: {NOMBRE_ESTADO[r.estado_notificacion] ?? r.estado_notificacion}</div>
              </div>
              {r.multimedia.length > 0 && (
                <div className="miniaturas">
                  {r.multimedia.map((m) => (
                    <button key={m.url} onClick={() => setFoto(m.url)} aria-label="Ver foto">
                      <img src={m.url} alt="Evidencia" loading="lazy" />
                    </button>
                  ))}
                </div>
              )}
            </li>
          ))}
          {reportes.datos && lista.length === 0 && <li className="vacio">Sin reportes en este periodo.</li>}
        </ul>
      )}
      {foto && (
        <div className="fondo-modal" onClick={() => setFoto(null)}>
          <img className="foto-grande" src={foto} alt="Evidencia" />
        </div>
      )}
    </>
  )
}

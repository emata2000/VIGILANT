import QRCode from 'qrcode'
import { useEffect, useState, type FormEvent } from 'react'
import { Circle, Marker, Polygon, Tooltip, useMapEvents } from 'react-leaflet'
import { api, type Geocerca, type PuntoControl } from '../api'
import { anilloAVertices, Mapa, type LatLng } from '../componentes/Mapa'
import { Modal } from '../componentes/Modal'
import { useCarga } from '../useCarga'

function codigoNuevo() {
  return 'QR-' + crypto.randomUUID().replace(/-/g, '').slice(0, 10).toUpperCase()
}

export function Puntos() {
  const puntos = useCarga(() => api<PuntoControl[]>('/v1/puntos-control'))
  const naves = useCarga(() => api<Geocerca[]>('/v1/geocercas'))
  const [nuevo, setNuevo] = useState<{ nombre_punto: string; codigo_uid: string; bodega_id: string; tolerancia_metros: number; pos: LatLng | null } | null>(null)
  const [qr, setQr] = useState<PuntoControl | null>(null)
  const [error, setError] = useState<string | null>(null)

  const nombreNave = (id: number | null) => naves.datos?.find((n) => n.id === id)?.nombre_bodega ?? 'Área común'
  const encuadre: LatLng[] = [
    ...(naves.datos ?? []).flatMap((g) => anilloAVertices(g.perimetro.coordinates[0])),
    ...(puntos.datos ?? []).map((p) => [p.coordenada_esperada.lat, p.coordenada_esperada.lng] as LatLng),
  ]

  async function guardar(e: FormEvent) {
    e.preventDefault()
    if (!nuevo) return
    if (!nuevo.pos) {
      setError('Toca el mapa donde estará pegado el código.')
      return
    }
    try {
      await api('/v1/puntos-control', {
        cuerpo: {
          nombre_punto: nuevo.nombre_punto,
          codigo_uid: nuevo.codigo_uid.trim(),
          bodega_id: nuevo.bodega_id ? Number(nuevo.bodega_id) : null,
          tolerancia_metros: nuevo.tolerancia_metros,
          coordenada_esperada: { lat: nuevo.pos[0], lng: nuevo.pos[1] },
        },
      })
      setNuevo(null)
      await puntos.recargar()
    } catch (err) {
      setError((err as Error).message)
    }
  }

  return (
    <>
      <div className="cabecera">
        <h1>Puntos de control</h1>
        {!nuevo && (
          <button
            className="btn primario"
            onClick={() => {
              setError(null)
              setNuevo({ nombre_punto: '', codigo_uid: codigoNuevo(), bodega_id: '', tolerancia_metros: 15, pos: null })
            }}
          >
            Nuevo punto
          </button>
        )}
      </div>
      <p className="ayuda">
        Cada punto es un código QR (o etiqueta NFC) pegado en la nave. El guardia lo escanea en su rondín para
        comprobar que pasó por ahí.
      </p>
      <div className={nuevo ? 'dividido' : ''}>
        <Mapa encuadre={nuevo ? undefined : encuadre}>
          {naves.datos?.map((g) => (
            <Polygon key={g.id} positions={anilloAVertices(g.perimetro.coordinates[0])} pathOptions={{ color: '#3b82f6', weight: 2 }} />
          ))}
          {puntos.datos?.map((p) => (
            <Circle
              key={p.id}
              center={[p.coordenada_esperada.lat, p.coordenada_esperada.lng]}
              radius={p.tolerancia_metros}
              pathOptions={{ color: '#22c55e' }}
            >
              <Tooltip>{p.nombre_punto}</Tooltip>
            </Circle>
          ))}
          {nuevo && <Selector pos={nuevo.pos} onPos={(pos) => setNuevo({ ...nuevo, pos })} />}
          {nuevo?.pos && <Circle center={nuevo.pos} radius={nuevo.tolerancia_metros} pathOptions={{ color: '#f59e0b' }} />}
        </Mapa>
        {nuevo && (
          <form className="formulario panel" onSubmit={guardar}>
            <h2>Nuevo punto</h2>
            <label>
              Nombre
              <input
                value={nuevo.nombre_punto}
                required
                placeholder="ej. Puerta norte B8"
                onChange={(e) => setNuevo({ ...nuevo, nombre_punto: e.target.value })}
              />
            </label>
            <label>
              Código (QR o UID del NFC)
              <input value={nuevo.codigo_uid} required onChange={(e) => setNuevo({ ...nuevo, codigo_uid: e.target.value })} />
            </label>
            <label>
              Nave
              <select value={nuevo.bodega_id} onChange={(e) => setNuevo({ ...nuevo, bodega_id: e.target.value })}>
                <option value="">Área común</option>
                {naves.datos?.map((n) => (
                  <option key={n.id} value={n.id}>
                    {n.nombre_bodega}
                  </option>
                ))}
              </select>
            </label>
            <label>
              Tolerancia del GPS (metros)
              <input
                type="number"
                min={1}
                max={500}
                value={nuevo.tolerancia_metros}
                onChange={(e) => setNuevo({ ...nuevo, tolerancia_metros: Number(e.target.value) })}
              />
            </label>
            <p className="ayuda">{nuevo.pos ? 'Ubicación marcada. Toca otra vez para moverla.' : 'Toca el mapa donde estará el código.'}</p>
            {error && <p className="error">{error}</p>}
            <div className="fila">
              <button className="btn primario">Guardar</button>
              <button type="button" className="btn" onClick={() => setNuevo(null)}>
                Cancelar
              </button>
            </div>
          </form>
        )}
      </div>
      <div className="tabla-envoltura">
        <table>
          <thead>
            <tr>
              <th>Punto</th>
              <th>Código</th>
              <th>Nave</th>
              <th />
            </tr>
          </thead>
          <tbody>
            {puntos.datos?.map((p) => (
              <tr key={p.id}>
                <td>{p.nombre_punto}</td>
                <td>
                  <code>{p.codigo_uid}</code>
                </td>
                <td>{nombreNave(p.bodega_id)}</td>
                <td className="derecha">
                  <button className="btn" onClick={() => setQr(p)}>
                    Ver QR
                  </button>
                </td>
              </tr>
            ))}
            {puntos.datos?.length === 0 && (
              <tr>
                <td colSpan={4} className="vacio">
                  Aún no hay puntos de control.
                </td>
              </tr>
            )}
          </tbody>
        </table>
      </div>
      {qr && <VerQr punto={qr} nave={nombreNave(qr.bodega_id)} onCerrar={() => setQr(null)} />}
    </>
  )
}

function Selector({ pos, onPos }: { pos: LatLng | null; onPos: (p: LatLng) => void }) {
  useMapEvents({ click: (e) => onPos([e.latlng.lat, e.latlng.lng]) })
  return pos ? <Marker position={pos} /> : null
}

function VerQr({ punto, nave, onCerrar }: { punto: PuntoControl; nave: string; onCerrar: () => void }) {
  const [src, setSrc] = useState('')
  useEffect(() => {
    void QRCode.toDataURL(punto.codigo_uid, { width: 480, margin: 2 }).then(setSrc)
  }, [punto.codigo_uid])
  return (
    <Modal titulo={punto.nombre_punto} onCerrar={onCerrar}>
      <div className="qr-imprimible">
        {src && <img src={src} alt={`QR ${punto.codigo_uid}`} />}
        <strong>{punto.nombre_punto}</strong>
        <span>
          {nave} · {punto.codigo_uid}
        </span>
      </div>
      <div className="fila">
        <button className="btn primario" onClick={() => window.print()}>
          Imprimir
        </button>
        {src && (
          <a className="btn" href={src} download={`${punto.codigo_uid}.png`}>
            Descargar PNG
          </a>
        )}
      </div>
    </Modal>
  )
}

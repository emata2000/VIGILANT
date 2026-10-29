import { useState, type FormEvent } from 'react'
import { Polygon, Tooltip } from 'react-leaflet'
import { api, type Geocerca, type Usuario } from '../api'
import { anilloAVertices, EditorPoligono, Mapa, verticesAAnillo, type LatLng } from '../componentes/Mapa'
import { useSesion } from '../sesion'
import { useCarga } from '../useCarga'

interface Borrador {
  id: number | null
  nombre_bodega: string
  num_bodega: string
  cliente_id: string
  vertices: LatLng[]
}

export function Naves() {
  const { sesion } = useSesion()
  const esAdmin = sesion?.rol === 'ADMINISTRADOR'
  const naves = useCarga(() => api<Geocerca[]>('/v1/geocercas'))
  const duenos = useCarga(
    () => (esAdmin ? api<Usuario[]>('/v1/usuarios?rol=DUENO_NAVE') : Promise.resolve([] as Usuario[])),
    [esAdmin],
  )
  const [borrador, setBorrador] = useState<Borrador | null>(null)
  const [error, setError] = useState<string | null>(null)
  const [guardando, setGuardando] = useState(false)

  const nombreDueno = (id: number | null) => duenos.datos?.find((d) => d.id === id)?.nombre ?? (id ? `#${id}` : 'Sin dueño')
  const todos = (naves.datos ?? []).flatMap((g) => anilloAVertices(g.perimetro.coordinates[0]))

  function editar(g: Geocerca | null) {
    setError(null)
    setBorrador(
      g
        ? {
            id: g.id,
            nombre_bodega: g.nombre_bodega,
            num_bodega: g.num_bodega ?? '',
            cliente_id: g.cliente_id ? String(g.cliente_id) : '',
            vertices: anilloAVertices(g.perimetro.coordinates[0]),
          }
        : { id: null, nombre_bodega: '', num_bodega: '', cliente_id: '', vertices: [] },
    )
  }

  async function guardar(e: FormEvent) {
    e.preventDefault()
    if (!borrador) return
    if (borrador.vertices.length < 3) {
      setError('Marca al menos 3 esquinas de la nave en el mapa.')
      return
    }
    setGuardando(true)
    try {
      const cuerpo = {
        nombre_bodega: borrador.nombre_bodega,
        num_bodega: borrador.num_bodega || null,
        cliente_id: borrador.cliente_id ? Number(borrador.cliente_id) : null,
        perimetro: { type: 'Polygon', coordinates: [verticesAAnillo(borrador.vertices)] },
      }
      if (borrador.id) await api(`/v1/geocercas/${borrador.id}`, { metodo: 'PUT', cuerpo })
      else await api('/v1/geocercas', { cuerpo })
      setBorrador(null)
      await naves.recargar()
    } catch (err) {
      setError((err as Error).message)
    } finally {
      setGuardando(false)
    }
  }

  return (
    <>
      <div className="cabecera">
        <h1>{esAdmin ? 'Naves' : 'Mis naves'}</h1>
        {esAdmin && !borrador && (
          <button className="btn primario" onClick={() => editar(null)}>
            Nueva nave
          </button>
        )}
      </div>
      {naves.error && <p className="error">{naves.error}</p>}
      <div className={borrador ? 'dividido' : ''}>
        <div>
          <Mapa encuadre={borrador?.vertices.length ? undefined : todos} alto={borrador ? 520 : 420}>
            {naves.datos
              ?.filter((g) => g.id !== borrador?.id)
              .map((g) => (
                <Polygon
                  key={g.id}
                  positions={anilloAVertices(g.perimetro.coordinates[0])}
                  pathOptions={{ color: '#3b82f6', weight: 2 }}
                  eventHandlers={esAdmin && !borrador ? { click: () => editar(g) } : {}}
                >
                  <Tooltip sticky>
                    {g.nombre_bodega}
                    {esAdmin ? ` · ${nombreDueno(g.cliente_id)}` : ''}
                  </Tooltip>
                </Polygon>
              ))}
            {borrador && (
              <EditorPoligono vertices={borrador.vertices} onCambio={(v) => setBorrador({ ...borrador, vertices: v })} />
            )}
          </Mapa>
          {borrador && (
            <p className="ayuda">
              Toca el mapa en cada esquina de la nave, en orden. Arrastra un punto para corregirlo.
            </p>
          )}
        </div>
        {borrador && (
          <form className="formulario panel" onSubmit={guardar}>
            <h2>{borrador.id ? 'Editar nave' : 'Nueva nave'}</h2>
            <label>
              Nombre
              <input
                value={borrador.nombre_bodega}
                required
                placeholder="ej. Bodega 8"
                onChange={(e) => setBorrador({ ...borrador, nombre_bodega: e.target.value })}
              />
            </label>
            <label>
              Número
              <input value={borrador.num_bodega} onChange={(e) => setBorrador({ ...borrador, num_bodega: e.target.value })} />
            </label>
            <label>
              Dueño (recibe las alertas)
              <select value={borrador.cliente_id} onChange={(e) => setBorrador({ ...borrador, cliente_id: e.target.value })}>
                <option value="">Sin dueño</option>
                {duenos.datos?.map((d) => (
                  <option key={d.id} value={d.id}>
                    {d.nombre} ({d.email})
                  </option>
                ))}
              </select>
            </label>
            <div className="fila">
              <button
                type="button"
                className="btn"
                disabled={!borrador.vertices.length}
                onClick={() => setBorrador({ ...borrador, vertices: borrador.vertices.slice(0, -1) })}
              >
                Deshacer punto
              </button>
              <button type="button" className="btn" onClick={() => setBorrador({ ...borrador, vertices: [] })}>
                Borrar trazo
              </button>
            </div>
            {error && <p className="error">{error}</p>}
            <div className="fila">
              <button className="btn primario" disabled={guardando}>
                Guardar
              </button>
              <button type="button" className="btn" onClick={() => setBorrador(null)}>
                Cancelar
              </button>
            </div>
          </form>
        )}
      </div>
      {!borrador && (
        <div className="tabla-envoltura">
          <table>
            <thead>
              <tr>
                <th>Nave</th>
                <th>Número</th>
                {esAdmin && <th>Dueño</th>}
                {esAdmin && <th />}
              </tr>
            </thead>
            <tbody>
              {naves.datos?.map((g) => (
                <tr key={g.id}>
                  <td>{g.nombre_bodega}</td>
                  <td>{g.num_bodega ?? '—'}</td>
                  {esAdmin && <td>{nombreDueno(g.cliente_id)}</td>}
                  {esAdmin && (
                    <td className="derecha">
                      <button className="btn" onClick={() => editar(g)}>
                        Editar
                      </button>
                    </td>
                  )}
                </tr>
              ))}
              {naves.datos?.length === 0 && (
                <tr>
                  <td colSpan={4} className="vacio">
                    {esAdmin ? 'Aún no hay naves. Crea la primera con “Nueva nave”.' : 'No tienes naves asignadas.'}
                  </td>
                </tr>
              )}
            </tbody>
          </table>
        </div>
      )}
    </>
  )
}

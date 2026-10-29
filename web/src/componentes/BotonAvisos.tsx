import { useEffect, useState } from 'react'
import { activarAvisos, estadoAvisos, type EstadoAvisos } from '../avisos'

/** Activa las notificaciones push del navegador para el usuario actual. */
export function BotonAvisos({ usuarioId }: { usuarioId: number }) {
  const [estado, setEstado] = useState<EstadoAvisos>('no-disponible')
  const [ocupado, setOcupado] = useState(false)

  useEffect(() => {
    void estadoAvisos().then((e) => {
      setEstado(e)
      // Si ya dio permiso, se renueva el token en silencio (Firebase lo rota).
      if (e === 'activos') void activarAvisos(usuarioId).catch(() => {})
    })
  }, [usuarioId])

  if (estado === 'no-disponible' || estado === 'activos') return null
  if (estado === 'bloqueados')
    return (
      <span className="etiqueta" title="Permite las notificaciones de este sitio en la configuración del navegador">
        Avisos bloqueados
      </span>
    )
  return (
    <button
      className="btn btn-avisos"
      disabled={ocupado}
      onClick={async () => {
        setOcupado(true)
        try {
          const ok = await activarAvisos(usuarioId)
          setEstado(ok ? 'activos' : await estadoAvisos())
        } catch {
          setEstado(await estadoAvisos())
        } finally {
          setOcupado(false)
        }
      }}
    >
      🔔 Activar avisos
    </button>
  )
}

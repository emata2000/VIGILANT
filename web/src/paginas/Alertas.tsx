import { useState, type FormEvent } from 'react'
import { api, type ConfigAlertas } from '../api'
import { useCarga } from '../useCarga'

export function Alertas() {
  const { datos, error, setDatos } = useCarga(() => api<ConfigAlertas>('/v1/me/alertas'))
  const [estado, setEstado] = useState<string | null>(null)
  const wa = useCarga(() =>
    api<{ whatsapp_habilitado: boolean }>('/v1/push/config').then((c) => c.whatsapp_habilitado).catch(() => false),
  )
  const conWhatsapp = wa.datos === true

  if (!datos) return error ? <p className="error">{error}</p> : <p className="tenue">Cargando…</p>
  const set = (c: Partial<ConfigAlertas>) => {
    setDatos({ ...datos, ...c })
    setEstado(null)
  }

  async function guardar(e: FormEvent) {
    e.preventDefault()
    try {
      setDatos(await api<ConfigAlertas>('/v1/me/alertas', { metodo: 'PUT', cuerpo: datos }))
      setEstado('Guardado')
    } catch (err) {
      setEstado((err as Error).message)
    }
  }

  const casilla = (campo: keyof ConfigAlertas, texto: string) => (
    <label className="casilla">
      <input type="checkbox" checked={datos[campo] as boolean} onChange={(e) => set({ [campo]: e.target.checked })} />
      {texto}
    </label>
  )

  return (
    <form className="formulario ancho" onSubmit={guardar}>
      <h1>Alertas</h1>
      <p className="ayuda">Para recibir avisos en este dispositivo, toca “🔔 Activar avisos” arriba.</p>
      <section className="panel">
        <h2>Emergencias</h2>
        <p className="ayuda">Las emergencias siempre se envían, aunque el horario de silencio esté activo.</p>
        {casilla('recibir_emergencia_push', 'Notificación en el teléfono')}
        {conWhatsapp && casilla('recibir_emergencia_whatsapp', 'WhatsApp')}
      </section>
      <section className="panel">
        <h2>Rondines</h2>
        {casilla('recibir_rutina_push', 'Notificación en el teléfono')}
        {conWhatsapp && casilla('recibir_rutina_whatsapp', 'WhatsApp')}
      </section>
      <section className="panel">
        <h2>Horario de silencio</h2>
        {casilla('modo_mute_activo', 'No avisarme de rondines en este horario')}
        <div className="fila">
          <label>
            Desde
            <input
              type="time"
              value={datos.mute_inicio_hora.slice(0, 5)}
              disabled={!datos.modo_mute_activo}
              onChange={(e) => set({ mute_inicio_hora: e.target.value })}
            />
          </label>
          <label>
            Hasta
            <input
              type="time"
              value={datos.mute_fin_hora.slice(0, 5)}
              disabled={!datos.modo_mute_activo}
              onChange={(e) => set({ mute_fin_hora: e.target.value })}
            />
          </label>
        </div>
        <p className="ayuda">
          Los rondines silenciados quedan en la bitácora y al terminar el horario te llega un resumen de la noche.
        </p>
      </section>
      <div className="fila">
        <button className="btn primario">Guardar</button>
        {estado && <span className={estado === 'Guardado' ? 'ok' : 'error'}>{estado}</span>}
      </div>
    </form>
  )
}

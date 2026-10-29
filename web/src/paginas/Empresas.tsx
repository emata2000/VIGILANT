import { useState, type FormEvent } from 'react'
import { api, type Tenant } from '../api'
import { Modal } from '../componentes/Modal'
import { useCarga } from '../useCarga'

const ESTADO: Record<Tenant['status'], string> = { active: 'Activa', trial: 'Prueba', suspended: 'Suspendida' }

export function Empresas() {
  const { datos, error, recargar } = useCarga(() => api<Tenant[]>('/v1/tenants'))
  const [nueva, setNueva] = useState(false)
  const [adminPara, setAdminPara] = useState<Tenant | null>(null)

  return (
    <>
      <div className="cabecera">
        <h1>Empresas</h1>
        <button className="btn primario" onClick={() => setNueva(true)}>
          Nueva empresa
        </button>
      </div>
      {error && <p className="error">{error}</p>}
      <div className="tabla-envoltura">
        <table>
          <thead>
            <tr>
              <th>Empresa</th>
              <th>Clave de acceso</th>
              <th>Zona horaria</th>
              <th>Estado</th>
              <th />
            </tr>
          </thead>
          <tbody>
            {datos?.map((t) => (
              <tr key={t.id}>
                <td>{t.nombre_comercial}</td>
                <td>
                  <code>{t.slug}</code>
                </td>
                <td>{t.zona_horaria}</td>
                <td>{ESTADO[t.status]}</td>
                <td className="derecha">
                  <button className="btn" onClick={() => setAdminPara(t)}>
                    Crear administrador
                  </button>
                </td>
              </tr>
            ))}
            {datos?.length === 0 && (
              <tr>
                <td colSpan={5} className="vacio">
                  Aún no hay empresas.
                </td>
              </tr>
            )}
          </tbody>
        </table>
      </div>
      {nueva && (
        <NuevaEmpresa
          onListo={() => {
            setNueva(false)
            void recargar()
          }}
          onCerrar={() => setNueva(false)}
        />
      )}
      {adminPara && <NuevoAdmin tenant={adminPara} onCerrar={() => setAdminPara(null)} />}
    </>
  )
}

function NuevaEmpresa({ onListo, onCerrar }: { onListo: () => void; onCerrar: () => void }) {
  const [f, setF] = useState({ nombre_comercial: '', slug: '', zona_horaria: 'America/Mexico_City', status: 'trial' })
  const [error, setError] = useState<string | null>(null)
  async function enviar(e: FormEvent) {
    e.preventDefault()
    try {
      await api('/v1/tenants', { cuerpo: f })
      onListo()
    } catch (err) {
      setError((err as Error).message)
    }
  }
  return (
    <Modal titulo="Nueva empresa" onCerrar={onCerrar}>
      <form onSubmit={enviar} className="formulario">
        <label>
          Nombre comercial
          <input
            value={f.nombre_comercial}
            required
            onChange={(e) => {
              const nombre = e.target.value
              const slug = nombre
                .toLowerCase()
                .normalize('NFD')
                .replace(/[̀-ͯ]/g, '')
                .replace(/[^a-z0-9]+/g, '-')
                .replace(/^-|-$/g, '')
              setF({ ...f, nombre_comercial: nombre, slug })
            }}
          />
        </label>
        <label>
          Clave de acceso (la escriben al iniciar sesión)
          <input value={f.slug} required pattern="[a-z0-9][a-z0-9\-]{1,58}[a-z0-9]" onChange={(e) => setF({ ...f, slug: e.target.value })} />
        </label>
        <label>
          Zona horaria
          <select value={f.zona_horaria} onChange={(e) => setF({ ...f, zona_horaria: e.target.value })}>
            {['America/Mexico_City', 'America/Monterrey', 'America/Chihuahua', 'America/Hermosillo', 'America/Tijuana', 'America/Cancun'].map(
              (z) => (
                <option key={z}>{z}</option>
              ),
            )}
          </select>
        </label>
        <label>
          Estado
          <select value={f.status} onChange={(e) => setF({ ...f, status: e.target.value })}>
            <option value="trial">Prueba</option>
            <option value="active">Activa</option>
            <option value="suspended">Suspendida</option>
          </select>
        </label>
        {error && <p className="error">{error}</p>}
        <button className="btn primario">Crear</button>
      </form>
    </Modal>
  )
}

function NuevoAdmin({ tenant, onCerrar }: { tenant: Tenant; onCerrar: () => void }) {
  const [f, setF] = useState({ nombre: '', email: '', password: '' })
  const [error, setError] = useState<string | null>(null)
  const [listo, setListo] = useState(false)
  async function enviar(e: FormEvent) {
    e.preventDefault()
    try {
      await api('/v1/usuarios', { cuerpo: { ...f, rol: 'ADMINISTRADOR', tenant_id: tenant.id } })
      setListo(true)
    } catch (err) {
      setError((err as Error).message)
    }
  }
  return (
    <Modal titulo={`Administrador de ${tenant.nombre_comercial}`} onCerrar={onCerrar}>
      {listo ? (
        <div className="formulario">
          <p>
            Listo. Puede entrar con la empresa <code>{tenant.slug}</code> y el correo {f.email}.
          </p>
          <button className="btn primario" onClick={onCerrar}>
            Cerrar
          </button>
        </div>
      ) : (
        <form onSubmit={enviar} className="formulario">
          <label>
            Nombre
            <input value={f.nombre} required onChange={(e) => setF({ ...f, nombre: e.target.value })} />
          </label>
          <label>
            Correo
            <input type="email" value={f.email} required onChange={(e) => setF({ ...f, email: e.target.value })} />
          </label>
          <label>
            Contraseña inicial
            <input value={f.password} required minLength={8} onChange={(e) => setF({ ...f, password: e.target.value })} />
          </label>
          {error && <p className="error">{error}</p>}
          <button className="btn primario">Crear administrador</button>
        </form>
      )}
    </Modal>
  )
}

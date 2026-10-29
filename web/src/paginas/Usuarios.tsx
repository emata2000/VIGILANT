import { useState, type FormEvent } from 'react'
import { api, NOMBRE_ROL, type Rol, type Usuario } from '../api'
import { Modal } from '../componentes/Modal'
import { useSesion } from '../sesion'
import { useCarga } from '../useCarga'

const ROLES: Rol[] = ['GUARDIA', 'DUENO_NAVE', 'ADMINISTRADOR']

export function Usuarios() {
  const { sesion } = useSesion()
  const { datos, error, recargar } = useCarga(() => api<Usuario[]>('/v1/usuarios'))
  const [filtro, setFiltro] = useState<Rol | 'todos'>('todos')
  const [editando, setEditando] = useState<Usuario | 'nuevo' | null>(null)
  const lista = datos?.filter((u) => filtro === 'todos' || u.rol === filtro) ?? []

  return (
    <>
      <div className="cabecera">
        <h1>Usuarios</h1>
        <button className="btn primario" onClick={() => setEditando('nuevo')}>
          Nuevo usuario
        </button>
      </div>
      <div className="pestanas">
        {(['todos', ...ROLES] as const).map((r) => (
          <button key={r} className={filtro === r ? 'activa' : ''} onClick={() => setFiltro(r)}>
            {r === 'todos' ? 'Todos' : NOMBRE_ROL[r]}
          </button>
        ))}
      </div>
      {error && <p className="error">{error}</p>}
      <div className="tabla-envoltura">
        <table>
          <thead>
            <tr>
              <th>Nombre</th>
              <th>Correo</th>
              <th>Rol</th>
              <th>WhatsApp</th>
              <th>Estado</th>
              <th />
            </tr>
          </thead>
          <tbody>
            {lista.map((u) => (
              <tr key={u.id} className={u.status !== 'active' ? 'apagado' : ''}>
                <td>{u.nombre}</td>
                <td>{u.email}</td>
                <td>{NOMBRE_ROL[u.rol]}</td>
                <td>{u.telefono_whatsapp ?? '—'}</td>
                <td>{u.status === 'active' ? 'Activo' : 'De baja'}</td>
                <td className="derecha">
                  <button className="btn" onClick={() => setEditando(u)}>
                    Editar
                  </button>
                </td>
              </tr>
            ))}
            {datos && lista.length === 0 && (
              <tr>
                <td colSpan={6} className="vacio">
                  Sin usuarios en esta categoría.
                </td>
              </tr>
            )}
          </tbody>
        </table>
      </div>
      {editando && (
        <FormUsuario
          usuario={editando === 'nuevo' ? null : editando}
          esYo={editando !== 'nuevo' && editando.id === sesion?.usuario_id}
          onCerrar={() => setEditando(null)}
          onListo={() => {
            setEditando(null)
            void recargar()
          }}
        />
      )}
    </>
  )
}

function FormUsuario({
  usuario,
  esYo,
  onCerrar,
  onListo,
}: {
  usuario: Usuario | null
  esYo: boolean
  onCerrar: () => void
  onListo: () => void
}) {
  const [f, setF] = useState({
    nombre: usuario?.nombre ?? '',
    email: usuario?.email ?? '',
    rol: (usuario?.rol ?? 'GUARDIA') as Rol,
    telefono_whatsapp: usuario?.telefono_whatsapp ?? '',
    password: '',
    activo: usuario ? usuario.status === 'active' : true,
  })
  const [error, setError] = useState<string | null>(null)

  async function enviar(e: FormEvent) {
    e.preventDefault()
    const telefono = f.telefono_whatsapp.replace(/[\s-]/g, '') || null
    try {
      if (usuario) {
        await api(`/v1/usuarios/${usuario.id}`, {
          metodo: 'PATCH',
          cuerpo: {
            nombre: f.nombre,
            telefono_whatsapp: telefono,
            status: f.activo ? 'active' : 'inactive',
            ...(f.password ? { password: f.password } : {}),
          },
        })
      } else {
        await api('/v1/usuarios', {
          cuerpo: { nombre: f.nombre, email: f.email, rol: f.rol, telefono_whatsapp: telefono, password: f.password },
        })
      }
      onListo()
    } catch (err) {
      setError((err as Error).message)
    }
  }

  return (
    <Modal titulo={usuario ? `Editar a ${usuario.nombre}` : 'Nuevo usuario'} onCerrar={onCerrar}>
      <form className="formulario" onSubmit={enviar}>
        <label>
          Nombre
          <input value={f.nombre} required onChange={(e) => setF({ ...f, nombre: e.target.value })} />
        </label>
        <label>
          Correo
          <input
            type="email"
            value={f.email}
            required
            disabled={!!usuario}
            onChange={(e) => setF({ ...f, email: e.target.value })}
          />
        </label>
        {!usuario && (
          <label>
            Rol
            <select value={f.rol} onChange={(e) => setF({ ...f, rol: e.target.value as Rol })}>
              {ROLES.map((r) => (
                <option key={r} value={r}>
                  {NOMBRE_ROL[r]}
                </option>
              ))}
            </select>
          </label>
        )}
        <label>
          WhatsApp (con lada internacional)
          <input
            value={f.telefono_whatsapp}
            placeholder="+5281…"
            inputMode="tel"
            onChange={(e) => setF({ ...f, telefono_whatsapp: e.target.value })}
          />
        </label>
        <label>
          {usuario ? 'Nueva contraseña (vacío = no cambiar)' : 'Contraseña inicial'}
          <input
            value={f.password}
            required={!usuario}
            minLength={8}
            onChange={(e) => setF({ ...f, password: e.target.value })}
          />
        </label>
        {usuario && !esYo && (
          <label className="casilla">
            <input type="checkbox" checked={f.activo} onChange={(e) => setF({ ...f, activo: e.target.checked })} />
            Activo (desmarca para dar de baja; ya no podrá entrar)
          </label>
        )}
        {error && <p className="error">{error}</p>}
        <button className="btn primario">{usuario ? 'Guardar' : 'Crear'}</button>
      </form>
    </Modal>
  )
}

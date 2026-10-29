import { NavLink, Outlet } from 'react-router-dom'
import { NOMBRE_ROL, type Rol } from '../api'
import { useSesion } from '../sesion'

const MENU: Record<Rol, { a: string; texto: string }[]> = {
  SUPER_ADMIN: [{ a: '/empresas', texto: 'Empresas' }],
  ADMINISTRADOR: [
    { a: '/bitacora', texto: 'Bitácora' },
    { a: '/naves', texto: 'Naves' },
    { a: '/puntos', texto: 'Puntos de control' },
    { a: '/usuarios', texto: 'Usuarios' },
  ],
  DUENO_NAVE: [
    { a: '/bitacora', texto: 'Bitácora' },
    { a: '/naves', texto: 'Mis naves' },
    { a: '/alertas', texto: 'Alertas' },
  ],
  GUARDIA: [],
}

export function Marco() {
  const { sesion, salir } = useSesion()
  if (!sesion) return <Outlet />
  return (
    <div className="marco">
      <header className="barra">
        <div className="marca">
          <img src="/favicon.svg" alt="" width={24} height={24} />
          <span>VIGILANT</span>
        </div>
        <nav>
          {MENU[sesion.rol].map((m) => (
            <NavLink key={m.a} to={m.a}>
              {m.texto}
            </NavLink>
          ))}
        </nav>
        <div className="quien">
          <span className="etiqueta">
            {NOMBRE_ROL[sesion.rol]}
            {sesion.empresa ? ` · ${sesion.empresa}` : ''}
          </span>
          <button className="btn-texto" onClick={salir}>
            Salir
          </button>
        </div>
      </header>
      <main className="contenido">
        <Outlet />
      </main>
    </div>
  )
}

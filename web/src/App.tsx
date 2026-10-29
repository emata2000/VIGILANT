import { BrowserRouter, Navigate, Route, Routes } from 'react-router-dom'
import type { Rol } from './api'
import { Marco } from './componentes/Marco'
import { ProveedorSesion, useSesion } from './sesion'
import { Login } from './paginas/Login'
import { lazy, Suspense, type ReactElement } from 'react'

// Carga por partes: el teléfono del guardia no descarga el mapa ni el panel.
const Empresas = lazy(() => import('./paginas/Empresas').then((m) => ({ default: m.Empresas })))
const Usuarios = lazy(() => import('./paginas/Usuarios').then((m) => ({ default: m.Usuarios })))
const Naves = lazy(() => import('./paginas/Naves').then((m) => ({ default: m.Naves })))
const Puntos = lazy(() => import('./paginas/Puntos').then((m) => ({ default: m.Puntos })))
const Bitacora = lazy(() => import('./paginas/Bitacora').then((m) => ({ default: m.Bitacora })))
const Alertas = lazy(() => import('./paginas/Alertas').then((m) => ({ default: m.Alertas })))
const Guardia = lazy(() => import('./guardia/Guardia').then((m) => ({ default: m.Guardia })))

const INICIO: Record<Rol, string> = {
  SUPER_ADMIN: '/empresas',
  ADMINISTRADOR: '/bitacora',
  DUENO_NAVE: '/bitacora',
  GUARDIA: '/guardia',
}

function Solo({ roles, children }: { roles: Rol[]; children: ReactElement }) {
  const { sesion } = useSesion()
  if (!sesion) return <Navigate to="/login" replace />
  if (!roles.includes(sesion.rol)) return <Navigate to={INICIO[sesion.rol]} replace />
  return <Suspense fallback={<p className="tenue" style={{ padding: '1rem' }}>Cargando…</p>}>{children}</Suspense>
}

function Rutas() {
  const { sesion } = useSesion()
  return (
    <Routes>
      <Route path="/login" element={sesion ? <Navigate to={INICIO[sesion.rol]} replace /> : <Login />} />
      <Route path="/guardia" element={<Solo roles={['GUARDIA']}><Guardia /></Solo>} />
      <Route element={<Marco />}>
        <Route path="/empresas" element={<Solo roles={['SUPER_ADMIN']}><Empresas /></Solo>} />
        <Route path="/usuarios" element={<Solo roles={['ADMINISTRADOR']}><Usuarios /></Solo>} />
        <Route path="/naves" element={<Solo roles={['ADMINISTRADOR', 'DUENO_NAVE']}><Naves /></Solo>} />
        <Route path="/puntos" element={<Solo roles={['ADMINISTRADOR']}><Puntos /></Solo>} />
        <Route path="/bitacora" element={<Solo roles={['ADMINISTRADOR', 'DUENO_NAVE']}><Bitacora /></Solo>} />
        <Route path="/alertas" element={<Solo roles={['DUENO_NAVE']}><Alertas /></Solo>} />
      </Route>
      <Route path="*" element={<Navigate to={sesion ? INICIO[sesion.rol] : '/login'} replace />} />
    </Routes>
  )
}

export default function App() {
  return (
    <ProveedorSesion>
      <BrowserRouter>
        <Rutas />
      </BrowserRouter>
    </ProveedorSesion>
  )
}

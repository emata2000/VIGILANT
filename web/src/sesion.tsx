import { createContext, useCallback, useContext, useEffect, useState, type ReactNode } from 'react'
import { guardarSesion, leerSesion, registrarAlExpirar, type Sesion } from './api'

interface Ctx {
  sesion: Sesion | null
  entrar: (s: Sesion) => void
  salir: () => void
}

const SesionCtx = createContext<Ctx>({ sesion: null, entrar: () => {}, salir: () => {} })

export function ProveedorSesion({ children }: { children: ReactNode }) {
  const [sesion, setSesion] = useState<Sesion | null>(() => leerSesion())
  const salir = useCallback(() => {
    guardarSesion(null)
    setSesion(null)
  }, [])
  useEffect(() => registrarAlExpirar(salir), [salir])
  return <SesionCtx.Provider value={{ sesion, entrar: setSesion, salir }}>{children}</SesionCtx.Provider>
}

export const useSesion = () => useContext(SesionCtx)

import { useCallback, useEffect, useState } from 'react'

/** Carga datos al montar y expone `recargar`. */
export function useCarga<T>(cargar: () => Promise<T>, deps: unknown[] = []) {
  const [datos, setDatos] = useState<T | null>(null)
  const [error, setError] = useState<string | null>(null)
  const [cargando, setCargando] = useState(true)
  const fn = useCallback(cargar, deps)
  const recargar = useCallback(async () => {
    setCargando(true)
    try {
      setDatos(await fn())
      setError(null)
    } catch (e) {
      setError((e as Error).message)
    } finally {
      setCargando(false)
    }
  }, [fn])
  useEffect(() => {
    void recargar()
  }, [recargar])
  return { datos, error, cargando, recargar, setDatos }
}

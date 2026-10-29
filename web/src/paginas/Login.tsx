import { useState, type FormEvent } from 'react'
import { iniciarSesion } from '../api'
import { useSesion } from '../sesion'

const LLAVE_EMPRESA = 'vigilant.empresa'

function empresaInicial(): string {
  const deUrl = new URLSearchParams(location.search).get('empresa')
  if (deUrl) return deUrl
  try {
    return localStorage.getItem(LLAVE_EMPRESA) ?? ''
  } catch {
    return ''
  }
}

export function Login() {
  const { entrar } = useSesion()
  const [empresa, setEmpresa] = useState(empresaInicial)
  const [email, setEmail] = useState('')
  const [password, setPassword] = useState('')
  const [error, setError] = useState<string | null>(null)
  const [enviando, setEnviando] = useState(false)

  async function enviar(e: FormEvent) {
    e.preventDefault()
    setEnviando(true)
    setError(null)
    try {
      const s = await iniciarSesion(empresa, email, password)
      try {
        localStorage.setItem(LLAVE_EMPRESA, empresa.trim())
      } catch {
        /* sin almacenamiento */
      }
      entrar(s)
    } catch (err) {
      setError((err as Error).message)
    } finally {
      setEnviando(false)
    }
  }

  return (
    <div className="login">
      <form className="tarjeta" onSubmit={enviar}>
        <div className="marca grande">
          <img src="/favicon.svg" alt="" width={36} height={36} />
          <span>VIGILANT</span>
        </div>
        <label>
          Empresa
          <input
            value={empresa}
            onChange={(e) => setEmpresa(e.target.value)}
            placeholder="ej. parque-norte"
            autoCapitalize="none"
            autoCorrect="off"
          />
        </label>
        <label>
          Correo
          <input type="email" value={email} onChange={(e) => setEmail(e.target.value)} required autoComplete="username" />
        </label>
        <label>
          Contraseña
          <input
            type="password"
            value={password}
            onChange={(e) => setPassword(e.target.value)}
            required
            autoComplete="current-password"
          />
        </label>
        {error && <p className="error">{error}</p>}
        <button className="btn primario" disabled={enviando}>
          {enviando ? 'Entrando…' : 'Entrar'}
        </button>
      </form>
    </div>
  )
}

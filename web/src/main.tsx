import { StrictMode } from 'react'
import { createRoot } from 'react-dom/client'
import './index.css'
import App from './App.tsx'

createRoot(document.getElementById('root')!).render(
  <StrictMode>
    <App />
  </StrictMode>,
)

// Service worker: abre la app sin señal y recibe push. Si ya hay uno (por ejemplo, con la
// configuración de Firebase), no se reemplaza.
if ('serviceWorker' in navigator && import.meta.env.PROD) {
  void navigator.serviceWorker
    .getRegistration()
    .then((r) => r ?? navigator.serviceWorker.register('/sw.js', { type: 'module' }))
    .catch(() => {})
}

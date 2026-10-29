import react from '@vitejs/plugin-react'
import { defineConfig } from 'vite'

// En desarrollo, /v1 se reenvía a la API local para no depender de CORS.
export default defineConfig({
  plugins: [react()],
  server: {
    host: true,
    proxy: {
      '/v1': process.env.VITE_PROXY_API ?? 'http://localhost:8000',
    },
  },
})

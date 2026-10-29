# VIGILANT · App web

Una sola app web para todos los roles. Cada quien ve lo suyo al iniciar sesión:

| Rol | Pantallas |
| --- | --- |
| Super admin | Empresas (tenants) y su primer administrador |
| Administrador | Bitácora (lista y mapa), naves dibujadas en el mapa, puntos de control con QR imprimible, usuarios (alta, edición, baja, reset de contraseña) |
| Dueño de nave | Bitácora de sus naves con fotos, mapa de sus naves, preferencias de alertas y horario de silencio |
| Guardia | Vista para teléfono: botón de emergencia, escaneo de QR con la cámara, rondín con foto y GPS del navegador, cola sin señal |

Stack: React 19 + TypeScript + Vite, React Router, Leaflet (mapas), jsQR (lector QR cuando el
navegador no trae `BarcodeDetector`), idb-keyval (cola sin señal en IndexedDB).

## Desarrollo

Con la API corriendo en `http://localhost:8000` (ver el README principal):

```bash
cd web
npm install
npm run dev        # http://localhost:5173, /v1 se reenvía a la API
```

Para entrar como super admin deja vacío el campo **Empresa**. Los demás usuarios escriben la
clave de su empresa (ej. `parque-norte`); también se puede prellenar con `?empresa=parque-norte`
en la URL para compartir el enlace con los guardias.

## Producción

```bash
VITE_API_URL=https://api.ejemplo.mx npm run build   # genera web/dist (archivos estáticos)
```

- `dist/` se sirve desde cualquier hosting estático. Configura que toda ruta desconocida
  responda `index.html` (la app usa rutas del navegador).
- En la API, agrega la URL pública del panel a `CORS_ORIGENES`, ej. `CORS_ORIGENES='["https://app.ejemplo.mx"]'`.
- **HTTPS es obligatorio** para la vista del guardia: sin él, el navegador no da acceso a la cámara ni al GPS.
- El bucket de fotos debe permitir `PUT` y `GET` desde el dominio del panel (regla CORS del bucket),
  porque el navegador sube la foto directo con la URL prefirmada.

## Notas de la vista del guardia

- La hora del reporte es cuando el guardia abre el formulario, no cuando llega al servidor.
- Si no hay señal, el reporte (con su foto) se guarda en el teléfono y se envía solo al volver
  la conexión. El `uuid_cliente` evita duplicados si se reenvía.
- Los puntos de control se descargan al entrar, para validar el QR aunque no haya señal.
- Si el navegador cierra la pestaña, la cola sigue guardada y se envía la próxima vez que se abra.
  Para envío en segundo plano con la pantalla apagada hará falta la app Android (fase 2).

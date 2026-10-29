# VIGILANT · App web

Una sola app web para todos los roles. Cada quien ve lo suyo al iniciar sesión:

| Rol | Pantallas |
| --- | --- |
| Super admin | Empresas (tenants) y su primer administrador |
| Administrador | Bitácora (lista y mapa), naves dibujadas en el mapa, puntos de control con QR imprimible, usuarios (alta, edición, baja, reset de contraseña) |
| Dueño de nave | Bitácora de sus naves con fotos, mapa de sus naves, preferencias de alertas y horario de silencio |
| Guardia | Vista para teléfono: botón de emergencia, escaneo de QR con la cámara, rondín con foto y GPS del navegador, cola sin señal, modo conducción y avisos por voz |

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

La forma recomendada (y gratuita) es una sola imagen Docker en la raíz del repo: compila esta
app y la API la sirve en el mismo dominio, así no hace falta CORS. Pasos en
[`docs/despliegue.md`](../docs/despliegue.md).

Para servirla aparte (hosting estático):

```bash
VITE_API_URL=https://api.ejemplo.mx npm run build   # genera web/dist
```

y agrega el dominio del panel a `CORS_ORIGENES` de la API. Toda ruta desconocida debe responder
`index.html`, y `sw.js` debe servirse desde la raíz.

- **HTTPS es obligatorio** para la vista del guardia (cámara y GPS).
- Notificaciones: el botón “🔔 Activar avisos” aparece cuando la API tiene configurado Firebase.
- La app se puede instalar en el teléfono (Agregar a pantalla principal) y abre sin señal.

## Notas de la vista del guardia

- La hora del reporte es cuando el guardia abre el formulario, no cuando llega al servidor.
- Si no hay señal, el reporte (con su foto) se guarda en el teléfono y se envía solo al volver
  la conexión. El `uuid_cliente` evita duplicados si se reenvía.
- Los puntos de control se descargan al entrar, para validar el QR aunque no haya señal.
- **Modo conducción:** arriba de 10 km/h la pantalla se bloquea; se desbloquea tras 3 s detenido.
  La emergencia sigue disponible manteniendo presionado el botón 2 segundos.
- A 25 m de un punto de control, el teléfono lo anuncia por voz.
- La pantalla no se apaga mientras la vista del guardia está abierta.
- Si el navegador cierra la pestaña, la cola sigue guardada y se envía la próxima vez que se abra.
  Para envío en segundo plano con la pantalla apagada hará falta la app Android (fase 2).

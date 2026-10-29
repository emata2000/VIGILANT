# Publicar VIGILANT gratis

Todo corre en planes gratuitos y con HTTPS incluido (necesario para la cámara y el GPS del guardia).
No hace falta comprar dominio: la app queda en `https://vigilant-xxxx.onrender.com`.

| Pieza | Servicio gratuito | Límite que importa |
| --- | --- | --- |
| API + app web | Render (1 servicio web) | Se duerme tras 15 min sin uso; despertar tarda ~1 min. Lo evitamos con un ping cada 10 min. 750 h al mes alcanzan para un servicio encendido todo el mes. |
| Base de datos + fotos | Supabase | 500 MB de base y 1 GB de fotos (unas 4,000–5,000 fotos de rondín comprimidas). El proyecto se pausa tras 7 días sin uso; el ping lo evita. Sin respaldos automáticos en el plan gratis. |
| Notificaciones push | Firebase Cloud Messaging | Gratis sin límite práctico. |
| Ping cada 10 min | cron-job.org | Gratis. |

WhatsApp queda apagado: si no se configuran sus llaves, las alertas van solo por push.

---

## 1. Supabase (base de datos y fotos)

1. Crea una cuenta en [supabase.com](https://supabase.com) y un proyecto nuevo. Región: la más cercana (por ejemplo, *East US*). Guarda la contraseña de la base.
2. Abre **SQL Editor**, pega el contenido de [`infra/supabase.sql`](../infra/supabase.sql), cambia `CAMBIA-ESTA-CONTRASEÑA` por una contraseña larga y ejecútalo. La última consulta debe mostrar `false | false`.
3. **Cadena de conexión:** botón **Connect** → **Session pooler**. Copia la URI y cámbiala así:
   - `postgresql://` → `postgresql+psycopg://`
   - usuario `postgres.<ref>` → `vigilant_app.<ref>`
   - la contraseña → la que pusiste en el paso 2

   Queda como `postgresql+psycopg://vigilant_app.abcd1234:TU-CLAVE@aws-0-us-east-1.pooler.supabase.com:5432/postgres`. Esto es `DATABASE_URL`.
4. **Fotos:** **Storage** → **New bucket** → nombre `vigilant-evidencias`, **privado**.
5. **Storage** → **Settings** → **S3 Connection**: activa la conexión y crea una **access key**. Anota:
   - Endpoint (`https://<ref>.supabase.co/storage/v1/s3`) → `S3_ENDPOINT_URL`
   - Región (ej. `us-east-1`) → `S3_REGION`
   - Access key ID → `S3_ACCESS_KEY`
   - Secret access key → `S3_SECRET_KEY`

## 2. Firebase (notificaciones push)

1. En [console.firebase.google.com](https://console.firebase.google.com) crea un proyecto (Google Analytics no es necesario).
2. **Agregar app** → **Web** (ícono `</>`), nombre `VIGILANT`. Copia el objeto `firebaseConfig` y conviértelo a JSON (comillas dobles en las llaves), por ejemplo:
   `{"apiKey":"AIza...","authDomain":"x.firebaseapp.com","projectId":"x","messagingSenderId":"123","appId":"1:123:web:abc"}`
   → `FIREBASE_WEB_CONFIG`
3. **Configuración del proyecto** → **Cloud Messaging** → **Certificados push web** → **Generar par de claves**. Copia la clave → `FIREBASE_VAPID_KEY`.
4. **Configuración del proyecto** → **Cuentas de servicio** → **Generar nueva clave privada**. Se descarga un `.json`; su contenido completo (todo el texto, en una línea o varias) → `FIREBASE_CREDENCIALES`. Guárdalo como secreto: da permiso de mandar notificaciones.

## 3. Render (API y app web)

1. Crea una cuenta en [render.com](https://render.com) con tu GitHub y dale acceso al repositorio `VIGILANT`.
2. **New** → **Blueprint** → elige el repositorio. Render lee [`render.yaml`](../render.yaml) y pide las variables:

   | Variable | Valor |
   | --- | --- |
   | `DATABASE_URL` | La del paso 1.3 |
   | `S3_ENDPOINT_URL`, `S3_REGION`, `S3_ACCESS_KEY`, `S3_SECRET_KEY` | Las del paso 1.5 |
   | `FIREBASE_WEB_CONFIG`, `FIREBASE_VAPID_KEY`, `FIREBASE_CREDENCIALES` | Las del paso 2 |
   | `PANEL_URL` | Por ahora vacío; ver paso 4 |
   | `CORS_ORIGENES` | `[]` (la app y la API comparten dominio) |
   | `SUPERADMIN_EMAIL`, `SUPERADMIN_PASSWORD` | Tu correo y una contraseña larga: se crea tu cuenta de super admin al arrancar |

   `JWT_SECRET` y `TAREAS_TOKEN` se generan solos.
3. Espera a que termine el primer despliegue (5–10 min). La URL aparece arriba, tipo `https://vigilant-xxxx.onrender.com`.
4. En **Environment**, pon `PANEL_URL` = esa URL (las notificaciones abren esa dirección al tocarlas) y guarda.
5. Al arrancar se crea tu cuenta de super admin con `SUPERADMIN_EMAIL` y `SUPERADMIN_PASSWORD`.
   Ya creada, puedes borrar `SUPERADMIN_PASSWORD` de Render (no se vuelve a usar).

## 4. Ping cada 10 minutos (cron-job.org)

Mantiene despiertos Render y Supabase, y manda el resumen matutino de rondines silenciados.

1. Cuenta gratis en [cron-job.org](https://cron-job.org) → **Create cronjob**.
2. URL: `https://vigilant-xxxx.onrender.com/v1/tareas/resumenes`
3. Cada 10 minutos. En **Advanced**: método **POST** y encabezado `X-Tarea-Token` con el valor de `TAREAS_TOKEN` (en Render → Environment).
4. Guarda y usa **Test run**: debe responder `200` con `{"resumenes_enviados": 0}`.

## 5. Primer uso

1. Entra a la URL con tu correo de super admin y la **Empresa vacía**. Crea la empresa y su administrador.
2. El administrador entra con la clave de la empresa, da de alta dueños y guardias, dibuja las naves, crea los puntos de control e imprime sus QR.
3. Dueños y administradores tocan **🔔 Activar avisos** y aceptan el permiso del navegador.
4. A los guardias compárteles `https://vigilant-xxxx.onrender.com/?empresa=CLAVE`. En Android Chrome: menú ⋮ → **Agregar a la pantalla principal**. Al abrirla por primera vez deben aceptar los permisos de cámara y ubicación.

## Cuándo pasar a pago

- Más de ~4,000 fotos o 500 MB de datos: Supabase Pro (US$25/mes) o mover las fotos a Cloudflare R2.
- Respaldos automáticos de la base: no existen en los planes gratis. Mientras tanto, desde la computadora: `pg_dump "$DATABASE_URL" > respaldo.sql` cada semana.
- Si el ping falla y Render se duerme, el primer reporte tardará ~1 min (la app del guardia lo reintenta sola).

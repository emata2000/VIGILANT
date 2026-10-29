# Payloads entre la app y la API

El contrato completo y siempre actualizado está en OpenAPI: `http://localhost:8000/docs`
(o `/openapi.json` para generar el cliente de la app). Esta página resume los flujos de la
app del guardia con ejemplos.

Todas las fechas van en ISO 8601 **con zona horaria**. Las coordenadas de ubicación van como
`{lat, lng}`; los polígonos de geocercas van en GeoJSON, que usa el orden `[lng, lat]`.

## 1. Iniciar sesión

`POST /v1/auth/login`

```json
{ "tenant": "parque-norte", "email": "guardia@norte.mx", "password": "..." }
```

Respuesta:

```json
{
  "access_token": "eyJhbGciOi...",
  "token_type": "bearer",
  "usuario_id": 3,
  "tenant_id": 1,
  "rol": "GUARDIA",
  "zona_horaria": "America/Monterrey"
}
```

Las demás llamadas llevan `Authorization: Bearer <access_token>`.

## 2. Registrar el teléfono para notificaciones push

`POST /v1/dispositivos` (al iniciar sesión y cada vez que Firebase rote el token)

```json
{ "fcm_token": "dQw4w9WgXcQ:APA91b...", "plataforma": "android" }
```

## 3. Descargar los puntos de control al iniciar turno

`GET /v1/puntos-control` devuelve la lista para validar NFC/QR sin señal.

## 4. Subir una foto

1. `POST /v1/multimedia/url` con `{ "content_type": "image/jpeg" }`
2. Respuesta: `{ "storage_key": "t1/0b6f...jpg", "url": "https://...", "metodo": "PUT", "expira_en_segundos": 900 }`
3. La app hace `PUT` de los bytes a `url` con el header `Content-Type: image/jpeg`.
4. La `storage_key` se incluye en el reporte.

Si la app está sin señal, guarda la foto local y repite estos pasos al recuperar conexión,
antes de enviar el reporte.

## 5. Enviar un reporte

`POST /v1/reportes`

```json
{
  "uuid_cliente": "6f1c2a8e-3b7d-4f6a-9c21-0d4e5f6a8b90",
  "tipo_evento": "RUTINA_PASO",
  "timestamp_campo": "2026-10-29T23:12:45-06:00",
  "ubicacion": { "lat": 25.7005, "lng": -100.2995, "precision_metros": 8.5 },
  "descripcion": "Sin novedades",
  "codigo_punto_control": "NFC-04A1B2",
  "multimedia": [{ "storage_key": "t1/0b6f...jpg", "tipo": "foto" }]
}
```

- `uuid_cliente`: lo genera la app **al crear** el reporte y lo guarda en la base local.
  Reenviar el mismo reporte devuelve `200` con `"duplicado": true` en vez de crear otro.
- `timestamp_campo`: la hora real del evento. La API rechaza fechas más de 5 minutos en el futuro.
- `ubicacion`: puede ser `null` si el GPS no obtuvo posición.
- `tipo_evento`: `RUTINA_PASO` o `ALERTA_EMERGENCIA`.

Respuesta `201`:

```json
{
  "id": 42,
  "uuid_cliente": "6f1c2a8e-3b7d-4f6a-9c21-0d4e5f6a8b90",
  "tipo_evento": "RUTINA_PASO",
  "timestamp_campo": "2026-10-30T05:12:45Z",
  "recibido_el": "2026-10-30T05:12:47Z",
  "guardia_id": 3,
  "ubicacion": { "lat": 25.7005, "lng": -100.2995 },
  "precision_metros": 8.5,
  "bodega_detectada_id": 7,
  "punto_control_id": 12,
  "estado_notificacion": "PENDIENTE",
  "descripcion": "Sin novedades",
  "duplicado": false
}
```

`estado_notificacion` pasa de `PENDIENTE` a uno de: `ENVIADO`, `SILENCIADO` (horario de mute),
`TARDIO` (rutina que llegó más de 30 minutos tarde), `SIN_DESTINATARIO`.

## 6. Sincronizar reportes guardados sin señal

`POST /v1/reportes/lote` con hasta 100 reportes:

```json
{ "reportes": [ { "uuid_cliente": "...", "tipo_evento": "RUTINA_PASO", "...": "..." } ] }
```

Respuesta: un resultado por reporte. La app borra de su base local los que tengan `ok: true`
y deja los demás para revisión.

```json
{
  "resultados": [
    { "uuid_cliente": "6f1c...", "ok": true, "reporte_id": 42, "duplicado": false, "error": null },
    { "uuid_cliente": "a7d2...", "ok": false, "reporte_id": null, "duplicado": false,
      "error": "Punto de control desconocido" }
  ]
}
```

## 7. Preferencias del dueño de nave

`GET /v1/me/alertas` y `PUT /v1/me/alertas`:

```json
{
  "recibir_rutina_whatsapp": false,
  "recibir_rutina_push": true,
  "recibir_emergencia_whatsapp": true,
  "recibir_emergencia_push": true,
  "modo_mute_activo": true,
  "mute_inicio_hora": "22:00:00",
  "mute_fin_hora": "06:00:00"
}
```

Las horas del mute se interpretan en la zona horaria del tenant.

# VIGILANT

SaaS multi-tenant de patrullaje vehicular: guardias en moto o carrito de golf registran
rondines y emergencias desde un teléfono Android rugerizado, el servidor ubica cada evento
en la geocerca de la bodega correspondiente y avisa al cliente por push o WhatsApp,
respetando su horario de silencio.

## Estado

| Componente | Estado |
| --- | --- |
| Esquema de base de datos (PostgreSQL + PostGIS, aislamiento por tenant con RLS) | Listo |
| API REST (FastAPI) | Listo: login, usuarios, geocercas, puntos de control, reportes, lotes offline, preferencias |
| Motor de alertas y mute (cola ARQ sobre Redis) | Listo, con envíos simulados en el log |
| Envío real por Firebase y WhatsApp Cloud API | Pendiente |
| App del guardia (Kotlin) | Pendiente |
| Panel web | Pendiente |

## Estructura

```
backend/            API FastAPI, worker de alertas, migraciones y pruebas
  app/models.py     Esquema (SQLAlchemy + GeoAlchemy2)
  app/schemas.py    Payloads JSON (contrato con la app)
  app/services/     Geocercas, reportes, motor de alertas, almacenamiento
  alembic/          Migraciones (incluye las políticas RLS)
docs/payloads.md    Ejemplos de los payloads de la app
docker-compose.yml  Postgres+PostGIS, Redis, MinIO, API y worker
```

## Levantar en local

Con Docker:

```bash
docker compose up --build
docker compose exec api python -m app.cli crear-superadmin root@vigilant.mx 'una-clave-segura'
```

Abre `http://localhost:8000/docs` para probar la API.

Sin Docker (necesitas PostgreSQL 16 con PostGIS y Redis):

```bash
cd backend
cp .env.example .env        # y ajusta los valores
uv sync
uv run alembic upgrade head
uv run uvicorn app.main:app --reload
uv run arq app.worker.WorkerSettings    # en otra terminal
```

## Pruebas

```bash
cd backend
uv run pytest
```

Las pruebas usan la base `vigilant_test` con PostGIS real y un rol sin superusuario,
para que Row-Level Security aplique igual que en producción.

## Decisiones respecto al PRD original

- **Aislamiento por tenant** en dos capas: cada consulta filtra por `tenant_id` y, además,
  PostgreSQL aplica Row-Level Security con el tenant del usuario autenticado.
- **`timestamp_campo`** (hora real del evento) separado de **`recibido_el`** (llegada al servidor).
- **`uuid_cliente`** en cada reporte para que los reintentos offline no dupliquen.
- **Zona horaria por tenant**; el mute se evalúa con la hora local del evento.
- **Emergencias** nunca se descartan: fuera de geocerca o sin GPS avisan a los administradores del tenant.
- Si el GPS cae **justo afuera** de una geocerca (20 m por defecto), se asigna a la bodega más cercana.
- Una **rutina que llega más de 30 minutos tarde** queda en bitácora sin notificar en tiempo real.
- Cada envío queda registrado en `notificaciones_enviadas`; si la cola reintenta, no se repiten avisos ya entregados.
- Un usuario puede tener **varios teléfonos** (`dispositivos_push`) y la unicidad de email es por tenant.

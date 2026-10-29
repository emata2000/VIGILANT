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
| App web (todos los roles, incluida la vista del guardia para teléfono) | Listo, ver [`web/README.md`](web/README.md) |
| App Android nativa del guardia | Fase 2 |

## Roles

| Rol | Quién es | Qué puede hacer |
| --- | --- | --- |
| `ADMINISTRADOR` | Administrador del parque o de la empresa de seguridad | Da de alta guardias y dueños, dibuja las naves (geocercas) y los checkpoints, ve toda la bitácora |
| `DUENO_NAVE` | Dueño o inquilino de una nave industrial | Recibe alertas de su nave, configura su horario de silencio, ve la bitácora de su nave |
| `GUARDIA` | Guardia en patrullaje | Envía rondines, escaneos y emergencias desde la app |

Además existe un `SUPER_ADMIN` interno, para el operador de la plataforma: da de alta empresas
nuevas (tenants) y su primer administrador. No se puede crear desde la API; solo con
`python -m app.cli crear-superadmin`.

## Estructura

```
backend/            API FastAPI, worker de alertas, migraciones y pruebas
  app/models.py     Esquema (SQLAlchemy + GeoAlchemy2)
  app/schemas.py    Payloads JSON (contrato con la app)
  app/services/     Geocercas, reportes, motor de alertas, almacenamiento
  alembic/          Migraciones (incluye las políticas RLS)
web/                App web (React + Vite) para todos los roles
docs/payloads.md    Ejemplos de los payloads de la app
docker-compose.yml  Postgres+PostGIS, Redis, MinIO, API y worker
```

## Levantar en local

Con Docker:

```bash
docker compose up --build
docker compose exec api python -m app.cli crear-superadmin root@vigilant.mx 'una-clave-segura'
```

Abre `http://localhost:8000/docs` para probar la API. Para que el panel pueda subir fotos,
crea el bucket `vigilant-evidencias` en la consola de MinIO (`http://localhost:9001`).

App web (en otra terminal):

```bash
cd web && npm install && npm run dev     # http://localhost:5173
```

Sin Docker (necesitas PostgreSQL 16 con PostGIS y Redis):

```bash
cd backend
cp .env.example .env        # y ajusta los valores
uv sync
uv run alembic upgrade head
uv run python -m app.cli crear-bucket   # bucket de fotos con CORS para el panel
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

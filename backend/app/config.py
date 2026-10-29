from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    # El rol de base de datos NO debe ser superusuario: los superusuarios se saltan RLS.
    database_url: str = "postgresql+psycopg://vigilant:vigilant@localhost:5432/vigilant"
    redis_url: str = "redis://localhost:6379/0"

    jwt_secret: str = "cambia-esto-en-produccion-con-32-bytes-o-mas"
    jwt_algoritmo: str = "HS256"
    jwt_minutos: int = 60 * 12

    # "cola": el procesamiento de alertas va a Redis (worker ARQ).
    # "sync": se procesa dentro de la misma petición (pruebas y desarrollo sin Redis).
    alertas_modo: str = "cola"

    # Un reporte de rutina que llega con más retraso que esto no se notifica en tiempo real.
    rutina_max_retraso_min: int = 30
    # Si el punto cae fuera de toda geocerca, se asigna la bodega más cercana dentro de este radio.
    geocerca_tolerancia_m: float = 20.0
    # Rechazar timestamps de campo que vengan del futuro por más de esto (reloj alterado).
    reloj_tolerancia_futuro_min: int = 5

    s3_bucket: str = "vigilant-evidencias"
    s3_endpoint_url: str | None = None
    # URL con la que el navegador o el teléfono llega al bucket (para las URLs prefirmadas).
    # Vacía = la misma que S3_ENDPOINT_URL. En Docker la interna es http://minio:9000.
    s3_endpoint_publico: str | None = None
    s3_region: str = "us-east-1"
    s3_access_key: str | None = None
    s3_secret_key: str | None = None
    s3_url_minutos: int = 15

    # Orígenes del panel web que pueden llamar a la API desde el navegador (CORS).
    # En producción, la URL pública del panel, ej. ["https://app.vigilant.mx"].
    cors_origenes: list[str] = ["http://localhost:5173"]
    # Carpeta con la app web compilada (web/dist). Si existe, la API también sirve el panel
    # en el mismo dominio (un solo servicio en el hosting gratuito).
    web_dir: str | None = None
    # Token para que un cron externo dispare tareas periódicas (resumen matutino) cuando
    # no hay worker. Vacío = endpoint desactivado.
    tareas_token: str | None = None
    # Si no existe ningún SUPER_ADMIN, se crea al arrancar con estos datos (útil en hosting
    # sin consola). Después de crearlo se pueden borrar.
    superadmin_email: str | None = None
    superadmin_password: str | None = None

    # URL pública del panel; las notificaciones push abren esta dirección.
    panel_url: str = "http://localhost:5173"

    # Firebase Cloud Messaging (push al navegador y a la app Android).
    # Cuenta de servicio: el JSON completo o la ruta al archivo.
    firebase_credenciales: str | None = None
    # Configuración web de Firebase (JSON de "Configuración del SDK") y clave VAPID.
    firebase_web_config: str | None = None
    firebase_vapid_key: str | None = None

    # WhatsApp Cloud API de Meta.
    whatsapp_token: str | None = None
    whatsapp_phone_id: str | None = None
    whatsapp_api_version: str = "v23.0"
    whatsapp_idioma: str = "es_MX"


@lru_cache
def get_settings() -> Settings:
    return Settings()

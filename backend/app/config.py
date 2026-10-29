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
    s3_region: str = "us-east-1"
    s3_access_key: str | None = None
    s3_secret_key: str | None = None
    s3_url_minutos: int = 15


@lru_cache
def get_settings() -> Settings:
    return Settings()

"""URLs prefirmadas de S3 (o compatible: MinIO, Cloudflare R2). La app sube la foto directo
al bucket y luego envía el reporte con la `storage_key`."""

import uuid
from functools import lru_cache

import boto3
from botocore.config import Config

from app.config import get_settings

_EXTENSIONES = {
    "image/jpeg": "jpg",
    "image/png": "png",
    "image/webp": "webp",
    "video/mp4": "mp4",
    "audio/mp4": "m4a",
}


@lru_cache
def _cliente():
    s = get_settings()
    return boto3.client(
        "s3",
        endpoint_url=s.s3_endpoint_url,
        region_name=s.s3_region,
        aws_access_key_id=s.s3_access_key,
        aws_secret_access_key=s.s3_secret_key,
        config=Config(signature_version="s3v4"),
    )


def nueva_llave(tenant_id: int, content_type: str) -> str:
    return f"t{tenant_id}/{uuid.uuid4()}.{_EXTENSIONES[content_type]}"


def llave_pertenece_a_tenant(storage_key: str, tenant_id: int) -> bool:
    return storage_key.startswith(f"t{tenant_id}/")


def url_subida(storage_key: str, content_type: str) -> tuple[str, int]:
    s = get_settings()
    segundos = s.s3_url_minutos * 60
    url = _cliente().generate_presigned_url(
        "put_object",
        Params={"Bucket": s.s3_bucket, "Key": storage_key, "ContentType": content_type},
        ExpiresIn=segundos,
    )
    return url, segundos


def url_lectura(storage_key: str, segundos: int = 7 * 24 * 3600) -> str:
    """URL temporal para ver la evidencia (por ejemplo, en el WhatsApp de emergencia)."""
    s = get_settings()
    return _cliente().generate_presigned_url(
        "get_object", Params={"Bucket": s.s3_bucket, "Key": storage_key}, ExpiresIn=segundos
    )

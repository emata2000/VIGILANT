"""Comandos de administración.

uv run python -m app.cli crear-superadmin root@vigilant.mx 'clave-segura'
uv run python -m app.cli crear-bucket http://localhost:5173
"""

import argparse

from app.db import sesion
from app.models import Usuario
from app.security import hash_password


def crear_superadmin(email: str, password: str) -> None:
    with sesion(bypass_rls=True) as db:
        db.add(
            Usuario(
                tenant_id=None,
                email=email.lower(),
                password_hash=hash_password(password),
                nombre="Super admin",
                rol="SUPER_ADMIN",
            )
        )
        db.commit()
    print(f"SUPER_ADMIN creado: {email}")


def crear_bucket(origenes: list[str]) -> None:
    """Crea el bucket de evidencias (si no existe) y permite que el navegador suba fotos."""
    from app.config import get_settings
    from app.services.storage import _cliente

    s = get_settings()
    s3 = _cliente()
    try:
        s3.head_bucket(Bucket=s.s3_bucket)
    except s3.exceptions.ClientError:
        s3.create_bucket(Bucket=s.s3_bucket)
    s3.put_bucket_cors(
        Bucket=s.s3_bucket,
        CORSConfiguration={
            "CORSRules": [
                {
                    "AllowedOrigins": origenes or s.cors_origenes,
                    "AllowedMethods": ["PUT", "GET"],
                    "AllowedHeaders": ["*"],
                    "MaxAgeSeconds": 3600,
                }
            ]
        },
    )
    print(f"Bucket listo: {s.s3_bucket}")


def main() -> None:
    p = argparse.ArgumentParser(prog="app.cli")
    sub = p.add_subparsers(dest="cmd", required=True)
    sa = sub.add_parser("crear-superadmin")
    sa.add_argument("email")
    sa.add_argument("password")
    cb = sub.add_parser("crear-bucket")
    cb.add_argument(
        "origenes", nargs="*", help="Orígenes del panel web (por defecto CORS_ORIGENES)"
    )
    args = p.parse_args()
    if args.cmd == "crear-superadmin":
        crear_superadmin(args.email, args.password)
    elif args.cmd == "crear-bucket":
        crear_bucket(args.origenes)


if __name__ == "__main__":
    main()

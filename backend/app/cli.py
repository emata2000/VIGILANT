"""Comandos de administración.

uv run python -m app.cli crear-superadmin root@vigilant.mx 'clave-segura'
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


def main() -> None:
    p = argparse.ArgumentParser(prog="app.cli")
    sub = p.add_subparsers(dest="cmd", required=True)
    sa = sub.add_parser("crear-superadmin")
    sa.add_argument("email")
    sa.add_argument("password")
    args = p.parse_args()
    if args.cmd == "crear-superadmin":
        crear_superadmin(args.email, args.password)


if __name__ == "__main__":
    main()

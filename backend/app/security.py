from datetime import UTC, datetime, timedelta

import bcrypt
import jwt

from app.config import get_settings


def hash_password(password: str) -> str:
    return bcrypt.hashpw(password.encode(), bcrypt.gensalt()).decode()


def verificar_password(password: str, password_hash: str) -> bool:
    try:
        return bcrypt.checkpw(password.encode(), password_hash.encode())
    except ValueError:
        return False


def crear_token(usuario_id: int, tenant_id: int | None, rol: str) -> str:
    s = get_settings()
    ahora = datetime.now(UTC)
    payload = {
        "sub": str(usuario_id),
        "tenant_id": tenant_id,
        "rol": rol,
        "iat": ahora,
        "exp": ahora + timedelta(minutes=s.jwt_minutos),
    }
    return jwt.encode(payload, s.jwt_secret, algorithm=s.jwt_algoritmo)


def decodificar_token(token: str) -> dict:
    s = get_settings()
    return jwt.decode(token, s.jwt_secret, algorithms=[s.jwt_algoritmo])

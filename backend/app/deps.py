from collections.abc import Callable, Iterator
from dataclasses import dataclass

import jwt
from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy.orm import Session

from app.db import sesion
from app.security import decodificar_token

_bearer = HTTPBearer(auto_error=False)


@dataclass(frozen=True)
class UsuarioActual:
    id: int
    tenant_id: int | None
    rol: str


def usuario_actual(
    cred: HTTPAuthorizationCredentials | None = Depends(_bearer),
) -> UsuarioActual:
    if cred is None:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Falta token de acceso")
    try:
        datos = decodificar_token(cred.credentials)
    except jwt.PyJWTError as e:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Token inválido o vencido") from e
    return UsuarioActual(id=int(datos["sub"]), tenant_id=datos.get("tenant_id"), rol=datos["rol"])


def db_tenant(usuario: UsuarioActual = Depends(usuario_actual)) -> Iterator[Session]:
    """Sesión limitada por RLS al tenant del usuario. SUPER_ADMIN ve todos los tenants."""
    with sesion(usuario.tenant_id, bypass_rls=usuario.rol == "SUPER_ADMIN") as db:
        yield db


def requiere_rol(*roles: str) -> Callable[[UsuarioActual], UsuarioActual]:
    def _verificar(usuario: UsuarioActual = Depends(usuario_actual)) -> UsuarioActual:
        if usuario.rol not in roles:
            raise HTTPException(status.HTTP_403_FORBIDDEN, "Tu rol no permite esta acción")
        return usuario

    return _verificar

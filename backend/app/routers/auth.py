from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db import sesion
from app.deps import UsuarioActual, db_tenant, usuario_actual
from app.models import Tenant, Usuario
from app.schemas import LoginIn, TokenOut, UsuarioOut
from app.security import crear_token, verificar_password

router = APIRouter(prefix="/v1/auth", tags=["auth"])


@router.post("/login", response_model=TokenOut)
def login(datos: LoginIn) -> TokenOut:
    # El login aún no conoce el tenant del usuario, así que usa bypass de RLS solo aquí.
    with sesion(bypass_rls=True) as db:
        tenant = None
        if datos.tenant:
            tenant = db.scalar(select(Tenant).where(Tenant.slug == datos.tenant))
            if tenant is None:
                raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Credenciales inválidas")
        usuario = db.scalar(
            select(Usuario).where(
                Usuario.email == datos.email.lower(),
                Usuario.tenant_id == tenant.id if tenant else Usuario.tenant_id.is_(None),
            )
        )
        if usuario is None or not verificar_password(datos.password, usuario.password_hash):
            raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Credenciales inválidas")
        if usuario.status != "active":
            raise HTTPException(status.HTTP_403_FORBIDDEN, "Usuario inactivo")
        if tenant is not None and tenant.status == "suspended":
            raise HTTPException(
                status.HTTP_403_FORBIDDEN, "La cuenta de la empresa está suspendida"
            )
        return TokenOut(
            access_token=crear_token(usuario.id, usuario.tenant_id, usuario.rol),
            usuario_id=usuario.id,
            tenant_id=usuario.tenant_id,
            rol=usuario.rol,
            zona_horaria=tenant.zona_horaria if tenant else None,
        )


@router.get("/me", response_model=UsuarioOut)
def yo(usuario: UsuarioActual = Depends(usuario_actual), db: Session = Depends(db_tenant)):
    u = db.get(Usuario, usuario.id)
    if u is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Usuario no encontrado")
    return u

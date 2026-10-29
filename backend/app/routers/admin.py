from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import func, select
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.deps import UsuarioActual, db_tenant, requiere_rol, usuario_actual
from app.models import ConfiguracionAlertas, DispositivoPush, Tenant, Usuario
from app.schemas import DispositivoIn, TenantIn, TenantOut, UsuarioIn, UsuarioOut
from app.security import hash_password

router = APIRouter(prefix="/v1", tags=["administración"])


@router.post("/tenants", response_model=TenantOut, status_code=201)
def crear_tenant(
    datos: TenantIn,
    _: UsuarioActual = Depends(requiere_rol("SUPER_ADMIN")),
    db: Session = Depends(db_tenant),
):
    t = Tenant(**datos.model_dump())
    db.add(t)
    try:
        db.commit()
    except IntegrityError as e:
        raise HTTPException(status.HTTP_409_CONFLICT, "Ya existe un tenant con ese slug") from e
    db.refresh(t)
    return t


@router.get("/tenants", response_model=list[TenantOut])
def listar_tenants(
    _: UsuarioActual = Depends(requiere_rol("SUPER_ADMIN")), db: Session = Depends(db_tenant)
):
    return db.scalars(select(Tenant).order_by(Tenant.id)).all()


@router.post("/usuarios", response_model=UsuarioOut, status_code=201)
def crear_usuario(
    datos: UsuarioIn,
    actual: UsuarioActual = Depends(requiere_rol("SUPER_ADMIN", "ADMINISTRADOR")),
    db: Session = Depends(db_tenant),
):
    if actual.rol == "SUPER_ADMIN":
        if datos.tenant_id is None:
            raise HTTPException(422, "SUPER_ADMIN debe indicar tenant_id")
        tenant_id = datos.tenant_id
    else:
        tenant_id = actual.tenant_id
    u = Usuario(
        tenant_id=tenant_id,
        email=datos.email.lower(),
        password_hash=hash_password(datos.password),
        nombre=datos.nombre,
        telefono_whatsapp=datos.telefono_whatsapp,
        rol=datos.rol,
    )
    db.add(u)
    try:
        db.flush()
    except IntegrityError as e:
        raise HTTPException(status.HTTP_409_CONFLICT, "Ya existe un usuario con ese email") from e
    if u.rol == "DUENO_NAVE":
        # Toda cuenta de cliente nace con preferencias por defecto (evita prefs nulas).
        db.add(ConfiguracionAlertas(cliente_id=u.id, tenant_id=tenant_id))
    db.commit()
    db.refresh(u)
    return u


@router.get("/usuarios", response_model=list[UsuarioOut])
def listar_usuarios(
    rol: str | None = None,
    _: UsuarioActual = Depends(requiere_rol("SUPER_ADMIN", "ADMINISTRADOR")),
    db: Session = Depends(db_tenant),
):
    q = select(Usuario).order_by(Usuario.id)
    if rol:
        q = q.where(Usuario.rol == rol)
    return db.scalars(q).all()


@router.post("/dispositivos", status_code=204)
def registrar_dispositivo(
    datos: DispositivoIn,
    actual: UsuarioActual = Depends(usuario_actual),
    db: Session = Depends(db_tenant),
):
    """La app llama esto al iniciar sesión y cada vez que Firebase rota el token."""
    if actual.tenant_id is None:
        raise HTTPException(422, "SUPER_ADMIN no recibe notificaciones")
    stmt = insert(DispositivoPush).values(
        tenant_id=actual.tenant_id,
        usuario_id=actual.id,
        fcm_token=datos.fcm_token,
        plataforma=datos.plataforma,
    )
    # Si el token ya existía (teléfono que cambió de usuario), se reasigna.
    db.execute(
        stmt.on_conflict_do_update(
            index_elements=["fcm_token"],
            set_={
                "usuario_id": stmt.excluded.usuario_id,
                "tenant_id": stmt.excluded.tenant_id,
                "ultimo_uso": func.now(),
            },
        )
    )
    db.commit()

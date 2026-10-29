from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.deps import UsuarioActual, db_tenant, requiere_rol
from app.models import ConfiguracionAlertas
from app.schemas import ConfigAlertasIO

router = APIRouter(prefix="/v1/me", tags=["preferencias de alertas"])

_dueno = requiere_rol("DUENO_NAVE")


def _obtener(db: Session, actual: UsuarioActual) -> ConfiguracionAlertas:
    cfg = db.get(ConfiguracionAlertas, actual.id)
    if cfg is None:
        cfg = ConfiguracionAlertas(cliente_id=actual.id, tenant_id=actual.tenant_id)
        db.add(cfg)
        db.commit()
        db.refresh(cfg)
    return cfg


@router.get("/alertas", response_model=ConfigAlertasIO)
def ver_preferencias(actual: UsuarioActual = Depends(_dueno), db: Session = Depends(db_tenant)):
    return _obtener(db, actual)


@router.put("/alertas", response_model=ConfigAlertasIO)
def guardar_preferencias(
    datos: ConfigAlertasIO,
    actual: UsuarioActual = Depends(_dueno),
    db: Session = Depends(db_tenant),
):
    cfg = _obtener(db, actual)
    for campo, valor in datos.model_dump().items():
        setattr(cfg, campo, valor)
    db.commit()
    db.refresh(cfg)
    return cfg

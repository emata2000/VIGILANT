"""Resumen matutino: al terminar su horario de silencio, el dueño de nave recibe cuántos
rondines se hicieron mientras dormía (esos rondines no se le notificaron en tiempo real).

El worker llama a `enviar_resumenes()` cada 5 minutos. Cada cliente recibe a lo más un
resumen por día local, gracias a la restricción única de `resumenes_enviados`.
"""

import logging
from collections import Counter
from datetime import UTC, date, datetime, time, timedelta
from zoneinfo import ZoneInfo

from sqlalchemy import select
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.orm import Session

from app.db import sesion
from app.models import (
    BodegaGeocerca,
    ConfiguracionAlertas,
    DispositivoPush,
    ReporteGuardia,
    ResumenEnviado,
    Tenant,
    Usuario,
)
from app.services.notificadores import Notificador, obtener_notificador

log = logging.getLogger("vigilant.resumen")

# Ventana después del fin del mute en la que se intenta mandar el resumen.
VENTANA = timedelta(minutes=30)
PLANTILLA_WHATSAPP = "plantilla_resumen_v1"


def ventana_silencio(
    fecha: date, inicio: time, fin: time, zona: ZoneInfo
) -> tuple[datetime, datetime]:
    """Inicio y fin (UTC) del periodo de silencio que termina en `fecha` a la hora `fin`."""
    fin_local = datetime.combine(fecha, fin, zona)
    dia_inicio = fecha if inicio < fin else fecha - timedelta(days=1)
    inicio_local = datetime.combine(dia_inicio, inicio, zona)
    return inicio_local.astimezone(UTC), fin_local.astimezone(UTC)


def texto_resumen(conteo: Counter[str]) -> str:
    total = sum(conteo.values())
    detalle = ", ".join(f"{n} en {nave}" for nave, n in conteo.most_common())
    plural = "rondín" if total == 1 else "rondines"
    return f"{total} {plural} sin novedades durante la noche ({detalle})."


def enviar_resumenes(ahora: datetime | None = None, notificador: Notificador | None = None) -> int:
    """Envía los resúmenes que tocan ahora. Devuelve cuántos se enviaron."""
    ahora = ahora or datetime.now(UTC)
    notificador = notificador or obtener_notificador()
    enviados = 0
    with sesion(bypass_rls=True) as db:
        filas = db.execute(
            select(ConfiguracionAlertas, Tenant.zona_horaria)
            .join(Usuario, Usuario.id == ConfiguracionAlertas.cliente_id)
            .join(Tenant, Tenant.id == ConfiguracionAlertas.tenant_id)
            .where(
                ConfiguracionAlertas.modo_mute_activo.is_(True),
                Usuario.status == "active",
                Tenant.status != "suspended",
            )
        ).all()
        for cfg, zona_nombre in filas:
            if cfg.mute_inicio_hora == cfg.mute_fin_hora:
                continue
            zona = ZoneInfo(zona_nombre)
            local = ahora.astimezone(zona)
            fin_hoy = datetime.combine(local.date(), cfg.mute_fin_hora, zona)
            if not (fin_hoy <= local < fin_hoy + VENTANA):
                continue
            if _resumir(db, cfg, local.date(), zona, notificador):
                enviados += 1
    return enviados


def _resumir(
    db: Session, cfg: ConfiguracionAlertas, fecha: date, zona: ZoneInfo, notificador: Notificador
) -> bool:
    desde, hasta = ventana_silencio(fecha, cfg.mute_inicio_hora, cfg.mute_fin_hora, zona)
    naves = db.execute(
        select(BodegaGeocerca.nombre_bodega)
        .join(ReporteGuardia, ReporteGuardia.bodega_detectada_id == BodegaGeocerca.id)
        .where(
            BodegaGeocerca.cliente_id == cfg.cliente_id,
            ReporteGuardia.estado_notificacion == "SILENCIADO",
            ReporteGuardia.timestamp_campo >= desde,
            ReporteGuardia.timestamp_campo < hasta,
        )
    ).scalars()
    conteo = Counter(naves)

    # Reservar el día antes de enviar: si otro worker ya lo tomó, no se repite.
    reservado = db.execute(
        insert(ResumenEnviado)
        .values(
            tenant_id=cfg.tenant_id,
            cliente_id=cfg.cliente_id,
            fecha=fecha,
            rondines=sum(conteo.values()),
        )
        .on_conflict_do_nothing(index_elements=["cliente_id", "fecha"])
        .returning(ResumenEnviado.id)
    ).scalar()
    db.commit()
    if reservado is None or not conteo:
        return False

    texto = texto_resumen(conteo)
    algo = False
    if cfg.recibir_rutina_push:
        tokens = list(
            db.scalars(
                select(DispositivoPush.fcm_token).where(
                    DispositivoPush.usuario_id == cfg.cliente_id
                )
            )
        )
        if tokens:
            try:
                notificador.enviar_push(tokens, "Resumen de la noche", texto, {"tipo": "RESUMEN"})
                algo = True
            except Exception as e:  # un canal caído no detiene a los demás
                log.warning("Resumen push a %s falló: %s", cfg.cliente_id, e)
    if cfg.recibir_rutina_whatsapp:
        telefono = db.scalar(select(Usuario.telefono_whatsapp).where(Usuario.id == cfg.cliente_id))
        if telefono:
            try:
                total = str(sum(conteo.values()))
                naves_txt = ", ".join(conteo)
                notificador.enviar_whatsapp(telefono, PLANTILLA_WHATSAPP, [total, naves_txt])
                algo = True
            except Exception as e:
                log.warning("Resumen WhatsApp a %s falló: %s", cfg.cliente_id, e)
    return algo

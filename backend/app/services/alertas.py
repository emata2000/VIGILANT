"""Motor de alertas: decide a quién avisar y por qué canal, y ejecuta los envíos.

`decidir()` es una función pura (sin base de datos) para poder probar cada regla.
`procesar_reporte()` la usa y registra cada envío en `notificaciones_enviadas`, de modo
que si la cola reintenta un trabajo no se duplican avisos ya entregados.

Cambios respecto al pseudocódigo del PRD:
- Una emergencia fuera de toda geocerca ya no se descarta: avisa a los TENANT_ADMIN.
- Las emergencias avisan siempre a los TENANT_ADMIN, además del cliente de la bodega.
- La hora del mute se toma de `timestamp_campo` en la zona horaria del tenant.
- El fin del mute es exclusivo (mute 22:00-06:00 ya no silencia las 06:00:00).
- Una rutina que llega con mucho retraso (sin señal) no se notifica en tiempo real.
"""

from dataclasses import dataclass, field
from datetime import UTC, datetime, time
from zoneinfo import ZoneInfo

from sqlalchemy import select
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.orm import Session

from app.config import get_settings
from app.models import (
    BodegaGeocerca,
    ConfiguracionAlertas,
    DispositivoPush,
    NotificacionEnviada,
    ReporteGuardia,
    ReporteMultimedia,
    Tenant,
    Usuario,
)
from app.services.notificadores import Notificador, obtener_notificador

# Decisión pendiente con el cliente: si es False (comportamiento del PRD), las emergencias
# llegan al cliente por push y WhatsApp aunque haya apagado esos canales.
EMERGENCIA_RESPETA_CANALES_CLIENTE = False


@dataclass(frozen=True)
class Preferencias:
    recibir_rutina_whatsapp: bool = False
    recibir_rutina_push: bool = True
    recibir_emergencia_whatsapp: bool = True
    recibir_emergencia_push: bool = True
    modo_mute_activo: bool = False
    mute_inicio_hora: time = time(22, 0)
    mute_fin_hora: time = time(6, 0)


@dataclass(frozen=True)
class Envio:
    usuario_id: int
    canal: str  # PUSH | WHATSAPP
    plantilla: str


@dataclass
class Decision:
    estado: str
    envios: list[Envio] = field(default_factory=list)


def en_horario_mute(hora: time, inicio: time, fin: time) -> bool:
    """Inicio inclusivo, fin exclusivo. inicio == fin significa ventana vacía."""
    if inicio == fin:
        return False
    if inicio < fin:
        return inicio <= hora < fin
    return hora >= inicio or hora < fin  # cruza la medianoche


def decidir(
    *,
    tipo_evento: str,
    cliente_id: int | None,
    prefs: Preferencias | None,
    admins: list[int],
    hora_local: time,
    retraso_min: float,
    max_retraso_rutina_min: float,
) -> Decision:
    prefs = prefs or Preferencias()

    if tipo_evento == "ALERTA_EMERGENCIA":
        # Las emergencias ignoran el mute y el retraso.
        envios: list[Envio] = []
        if cliente_id is not None:
            quiere_push = prefs.recibir_emergencia_push or not EMERGENCIA_RESPETA_CANALES_CLIENTE
            quiere_wa = prefs.recibir_emergencia_whatsapp or not EMERGENCIA_RESPETA_CANALES_CLIENTE
            if quiere_push:
                envios.append(Envio(cliente_id, "PUSH", "emergencia"))
            if quiere_wa:
                envios.append(Envio(cliente_id, "WHATSAPP", "plantilla_emergencia_v1"))
        for admin_id in admins:
            if admin_id == cliente_id:
                continue
            envios.append(Envio(admin_id, "PUSH", "emergencia"))
            envios.append(Envio(admin_id, "WHATSAPP", "plantilla_emergencia_v1"))
        return Decision("ENVIADO" if envios else "SIN_DESTINATARIO", envios)

    # RUTINA_PASO: solo al cliente dueño de la bodega.
    if cliente_id is None:
        return Decision("SIN_DESTINATARIO")
    if retraso_min > max_retraso_rutina_min:
        return Decision("TARDIO")
    if prefs.modo_mute_activo and en_horario_mute(
        hora_local, prefs.mute_inicio_hora, prefs.mute_fin_hora
    ):
        return Decision("SILENCIADO")
    envios = []
    if prefs.recibir_rutina_push:
        envios.append(Envio(cliente_id, "PUSH", "rutina"))
    if prefs.recibir_rutina_whatsapp:
        envios.append(Envio(cliente_id, "WHATSAPP", "plantilla_rutina_v1"))
    return Decision("ENVIADO" if envios else "SIN_DESTINATARIO", envios)


def _textos(plantilla: str, lugar: str) -> tuple[str, str]:
    if plantilla == "emergencia":
        return "ALERTA CRÍTICA", f"Incidencia grave en {lugar}"
    return "Rondín realizado", f"Inspección sin novedades en {lugar}"


def procesar_reporte(
    db: Session,
    reporte_id: int,
    *,
    ahora: datetime | None = None,
    notificador: Notificador | None = None,
    url_evidencia=None,
) -> Decision | None:
    """Evalúa un reporte y envía sus notificaciones. Seguro de reintentar."""
    s = get_settings()
    notificador = notificador or obtener_notificador()
    ahora = ahora or datetime.now(UTC)

    reporte = db.get(ReporteGuardia, reporte_id)
    if reporte is None:
        return None
    tenant = db.get(Tenant, reporte.tenant_id)
    bodega = (
        db.get(BodegaGeocerca, reporte.bodega_detectada_id) if reporte.bodega_detectada_id else None
    )
    cliente_id = bodega.cliente_id if bodega else None

    prefs = None
    if cliente_id is not None:
        fila = db.get(ConfiguracionAlertas, cliente_id)
        if fila is not None:
            prefs = Preferencias(**{k: getattr(fila, k) for k in Preferencias.__dataclass_fields__})

    admins = []
    if reporte.tipo_evento == "ALERTA_EMERGENCIA":
        admins = list(
            db.scalars(
                select(Usuario.id).where(
                    Usuario.tenant_id == reporte.tenant_id,
                    Usuario.rol == "TENANT_ADMIN",
                    Usuario.status == "active",
                )
            )
        )

    hora_local = reporte.timestamp_campo.astimezone(ZoneInfo(tenant.zona_horaria)).time()
    retraso_min = (ahora - reporte.timestamp_campo).total_seconds() / 60
    decision = decidir(
        tipo_evento=reporte.tipo_evento,
        cliente_id=cliente_id,
        prefs=prefs,
        admins=admins,
        hora_local=hora_local,
        retraso_min=retraso_min,
        max_retraso_rutina_min=s.rutina_max_retraso_min,
    )

    lugar = bodega.nombre_bodega if bodega else "área común del parque"
    evidencia = ""
    if url_evidencia is not None:
        key = db.scalar(
            select(ReporteMultimedia.storage_key)
            .where(ReporteMultimedia.reporte_id == reporte.id)
            .order_by(ReporteMultimedia.id)
            .limit(1)
        )
        evidencia = url_evidencia(key) if key else ""

    ya_enviados = set(
        db.execute(
            select(NotificacionEnviada.usuario_id, NotificacionEnviada.canal).where(
                NotificacionEnviada.reporte_id == reporte.id,
                NotificacionEnviada.estado == "ENVIADO",
            )
        )
    )

    algun_ok = False
    for envio in decision.envios:
        if (envio.usuario_id, envio.canal) in ya_enviados:
            algun_ok = True
            continue
        error = _enviar(db, notificador, envio, reporte, lugar, evidencia)
        algun_ok = algun_ok or error is None
        stmt = insert(NotificacionEnviada).values(
            tenant_id=reporte.tenant_id,
            reporte_id=reporte.id,
            usuario_id=envio.usuario_id,
            canal=envio.canal,
            plantilla=envio.plantilla,
            estado="ENVIADO" if error is None else "FALLIDO",
            error=error,
        )
        db.execute(
            stmt.on_conflict_do_update(
                index_elements=["reporte_id", "usuario_id", "canal"],
                set_={"estado": stmt.excluded.estado, "error": stmt.excluded.error},
            )
        )

    if decision.envios and not algun_ok:
        reporte.estado_notificacion = "PENDIENTE"  # todos fallaron: que la cola reintente
    else:
        reporte.estado_notificacion = decision.estado
    db.commit()
    return decision


def _enviar(
    db: Session,
    notificador: Notificador,
    envio: Envio,
    reporte: ReporteGuardia,
    lugar: str,
    evidencia: str,
) -> str | None:
    """Devuelve None si se envió, o el motivo del fallo."""
    try:
        if envio.canal == "PUSH":
            tokens = list(
                db.scalars(
                    select(DispositivoPush.fcm_token).where(
                        DispositivoPush.usuario_id == envio.usuario_id
                    )
                )
            )
            if not tokens:
                return "El usuario no tiene dispositivos registrados"
            titulo, cuerpo = _textos(envio.plantilla, lugar)
            notificador.enviar_push(
                tokens, titulo, cuerpo, {"reporte_id": str(reporte.id), "tipo": reporte.tipo_evento}
            )
        else:
            telefono = db.scalar(
                select(Usuario.telefono_whatsapp).where(Usuario.id == envio.usuario_id)
            )
            if not telefono:
                return "El usuario no tiene teléfono de WhatsApp"
            params = [lugar] + (
                [evidencia] if envio.plantilla.startswith("plantilla_emergencia") else []
            )
            notificador.enviar_whatsapp(telefono, envio.plantilla, params)
    except Exception as e:  # el fallo de un canal no debe impedir los demás
        return str(e) or e.__class__.__name__
    return None

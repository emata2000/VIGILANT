"""Canales de salida. Push (Firebase) y WhatsApp (Meta Cloud API) se conectan en la fase 3;
mientras tanto `NotificadorLog` escribe en el log y `NotificadorMemoria` sirve para pruebas."""

import logging
from dataclasses import dataclass, field
from typing import Protocol

log = logging.getLogger("vigilant.notificaciones")


class ErrorEnvio(Exception):
    pass


class Notificador(Protocol):
    def enviar_push(self, tokens: list[str], titulo: str, cuerpo: str, datos: dict) -> None: ...

    def enviar_whatsapp(self, telefono: str, plantilla: str, parametros: list[str]) -> None: ...


class NotificadorLog:
    def enviar_push(self, tokens: list[str], titulo: str, cuerpo: str, datos: dict) -> None:
        log.info("PUSH a %d dispositivo(s): %s | %s | %s", len(tokens), titulo, cuerpo, datos)

    def enviar_whatsapp(self, telefono: str, plantilla: str, parametros: list[str]) -> None:
        log.info("WHATSAPP a %s: %s %s", telefono, plantilla, parametros)


@dataclass
class NotificadorMemoria:
    push: list[dict] = field(default_factory=list)
    whatsapp: list[dict] = field(default_factory=list)
    fallar_whatsapp: bool = False

    def enviar_push(self, tokens: list[str], titulo: str, cuerpo: str, datos: dict) -> None:
        self.push.append({"tokens": tokens, "titulo": titulo, "cuerpo": cuerpo, "datos": datos})

    def enviar_whatsapp(self, telefono: str, plantilla: str, parametros: list[str]) -> None:
        if self.fallar_whatsapp:
            raise ErrorEnvio("WhatsApp no disponible")
        self.whatsapp.append(
            {"telefono": telefono, "plantilla": plantilla, "parametros": parametros}
        )


_notificador: Notificador = NotificadorLog()


def obtener_notificador() -> Notificador:
    return _notificador


def configurar_notificador(n: Notificador) -> None:
    global _notificador
    _notificador = n

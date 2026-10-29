from datetime import time

import pytest

from app.services.alertas import Preferencias, decidir, en_horario_mute


@pytest.mark.parametrize(
    ("hora", "esperado"),
    [
        (time(21, 59), False),
        (time(22, 0), True),
        (time(23, 30), True),
        (time(0, 0), True),
        (time(5, 59, 59), True),
        (time(6, 0), False),  # fin exclusivo (el PRD lo incluía)
        (time(12, 0), False),
    ],
)
def test_mute_que_cruza_medianoche(hora, esperado):
    assert en_horario_mute(hora, time(22, 0), time(6, 0)) is esperado


def test_mute_dentro_del_dia_y_ventana_vacia():
    assert en_horario_mute(time(14, 0), time(13, 0), time(15, 0))
    assert not en_horario_mute(time(15, 0), time(13, 0), time(15, 0))
    assert not en_horario_mute(time(13, 0), time(13, 0), time(13, 0))


def _decidir(**kw):
    base = dict(
        tipo_evento="RUTINA_PASO",
        cliente_id=10,
        prefs=Preferencias(),
        admins=[1],
        hora_local=time(12, 0),
        retraso_min=0,
        max_retraso_rutina_min=30,
    )
    base.update(kw)
    return decidir(**base)


def test_rutina_por_defecto_solo_push_al_cliente():
    d = _decidir()
    assert d.estado == "ENVIADO"
    assert [(e.usuario_id, e.canal) for e in d.envios] == [(10, "PUSH")]


def test_rutina_en_mute_queda_silenciada():
    prefs = Preferencias(modo_mute_activo=True)
    assert _decidir(prefs=prefs, hora_local=time(23, 0)).estado == "SILENCIADO"
    assert _decidir(prefs=prefs, hora_local=time(7, 0)).estado == "ENVIADO"


def test_rutina_tardia_no_se_notifica():
    assert _decidir(retraso_min=45).estado == "TARDIO"


def test_rutina_sin_cliente_o_con_canales_apagados():
    assert _decidir(cliente_id=None).estado == "SIN_DESTINATARIO"
    apagado = Preferencias(recibir_rutina_push=False, recibir_rutina_whatsapp=False)
    assert _decidir(prefs=apagado).estado == "SIN_DESTINATARIO"


def test_emergencia_ignora_mute_y_retraso_y_avisa_a_admins():
    prefs = Preferencias(modo_mute_activo=True)
    d = _decidir(
        tipo_evento="ALERTA_EMERGENCIA", prefs=prefs, hora_local=time(3, 0), retraso_min=120
    )
    assert d.estado == "ENVIADO"
    assert {(e.usuario_id, e.canal) for e in d.envios} == {
        (10, "PUSH"),
        (10, "WHATSAPP"),
        (1, "PUSH"),
        (1, "WHATSAPP"),
    }


def test_emergencia_fuera_de_geocerca_avisa_a_admins():
    d = _decidir(tipo_evento="ALERTA_EMERGENCIA", cliente_id=None, admins=[1, 2])
    assert d.estado == "ENVIADO"
    assert {e.usuario_id for e in d.envios} == {1, 2}

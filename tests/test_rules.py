import numpy as np
import pandas as pd
import pytest
from conftest import AS_OF

from lct.rules import (business_days_between, delay_bucket, incident_category, is_critical, leg_sla_status, route,
                       sent_date)


def test_sent_date_is_next_business_day():
    sent = sent_date(pd.to_datetime(["2026-06-25", "2026-06-26"]))  # Thursday, Friday
    assert [str(d) for d in sent] == ["2026-06-26", "2026-06-29"]   # Friday, next Monday


def test_business_days_skip_weekends():
    days = business_days_between(pd.to_datetime(["2026-06-26", "2026-06-26"]), pd.to_datetime(["2026-06-30", None]))
    assert days[0] == 2          # Friday and Monday
    assert pd.isna(days[1])      # unknown end date


def test_calculated_columns(master):
    by_order = master.set_index("Documento de ventas")
    assert by_order["Dias Habiles Transcurridos"].loc[26100001] == 1
    assert by_order["Dias Habiles Transcurridos"].loc[26100004] == 16   # counted from the pick-up date
    assert by_order["Es Critica"].to_dict() == {
        26100001: False, 26100002: True, 26100003: True, 26100004: True,
        26100005: False, 26100006: False, 26100007: False, 26100008: False,
    }
    assert by_order["DIAS DE ATRASO"].loc[26100006] == 11              # stops at arrival at the depot
    assert by_order["DIAS DE ATRASO"].loc[26100004] == 29              # still running: until the snapshot date
    assert pd.isna(by_order["DIAS DE ATRASO"].loc[26100007])            # purged


def test_leg_sla_status(master):
    legs = leg_sla_status(master, AS_OF)
    legs.index = master["Documento de ventas"]
    assert legs.loc[26100001, "pickup_sla_status"] == "En curso"         # 1 bd so far, SLA 2
    assert legs.loc[26100002, "pickup_sla_status"] == "Fuera de plazo"   # 3 bd, SLA 2
    assert legs.loc[26100004, "pickup_sla_status"] == "En plazo"         # sent 02/06, picked 08/06: 4 bd, SLA 10
    assert legs.loc[26100004, "depot_sla_status"] == "Fuera de plazo"    # 16 bd since pick-up, reaches SLA 15
    assert legs.loc[26100006, "depot_business_days"] == 5                # 05/06 -> 12/06
    assert legs.loc[26100006, "depot_sla_status"] == "En plazo"          # SLA 7
    assert pd.isna(legs.loc[26100001, "depot_sla_status"])                # not picked up yet
    assert pd.isna(legs.loc[26100007, "pickup_sla_status"])               # purged: not measured


@pytest.mark.parametrize("carrier, status, days, expected", [
    ("EXPRESO DELTA", "EN GESTION", 1, False),
    ("EXPRESO DELTA", "EN GESTION", 2, True),          # reaching the pick-up SLA makes it critical
    ("EXPRESO DELTA", "RETIRADO", 2, False),
    ("EXPRESO DELTA", "RETIRADO", 3, True),            # reaching the depot SLA makes it critical
    ("TRANSPORTES ANDINOS", "EN GESTION", 10, True),
    ("TRANSPORTES ANDINOS", "EN PUNTO DE CONTROL", 99, False),  # only pending orders can be critical
])
def test_critical_when_reaching_the_sla(carrier, status, days, expected):
    df = pd.DataFrame({"PROVEEDOR": [carrier], "ESTADO": [status]})
    assert bool(is_critical(df, np.array([days], dtype=float))[0]) is expected


@pytest.mark.parametrize("days, expected", [
    (0, "0 - 7 días"), (7, "0 - 7 días"), (8, "8 - 15 días"), (15, "8 - 15 días"), (16, "16 - 30 días"),
    (30, "16 - 30 días"), (31, "31 - 60 días"), (60, "31 - 60 días"), (61, "> 60 días"), (None, None),
])
def test_delay_bucket_limits(days, expected):
    assert delay_bucket([days]) == [expected]


@pytest.mark.parametrize("code, expected", [
    ("LGAR-Int-Andinos-Suc-Cordoba", "Interior"),
    ("LGAR-Bs.As. Costa-MAREA", "Costa Atlántica"),
    ("LGAR-GBA-Norte 1", "GBA"),
    ("LGAR-Capital-Oeste 1", "CABA"),
    ("LGAR-Otro", None),
    (None, None),
])
def test_route_from_route_code(code, expected):
    assert route(code) == expected


@pytest.mark.parametrize("note, expected", [
    (None, "Sin observación"),
    ("   ", "Sin observación"),
    ("duplicada 26100002", "Duplicada / Repetida"),
    ("SE REPITE CON 26100002", "Duplicada / Repetida"),          # duplicate wins over "con otra orden"
    ("CANTIDAD DIFIERE DE LO INFORMADO", "Diferencia de cantidad"),
    ("NADA PARA RETIRAR", "Retiro fallido / sin mercadería"),
    ("ELIMINADA A PEDIDO DE COMERCIAL", "Baja del cliente"),
    ("LOCAL CERRADO", "Cliente / local cerrado"),
    ("LA TRAE EL CLIENTE AL DEPOSITO", "Cliente entrega directo"),
    ("MERCADERIA DEVUELTA AL CLIENTE", "Retirada, devuelta al cliente"),
    ("RENDIDA CON OR 26100009", "Retirada / rendida con otra orden"),
    ("RETIRADA CON ORDEN", "Retirada / rendida con otra orden"),
    ("SE GENERO NUEVA ORDEN 26100010", "Nueva orden generada"),
    ("ESPERA DE INFORMACION DEL PROVEEDOR", "Espera de información del proveedor"),
    ("CLIENTE DE VACACIONES", "Cliente no disponible (temporal)"),
    ("DOCUMENTACION EN ADUANA", "Documentación / Aduana"),
    ("RETIRO REALIZADO, FALTA RENDIR", "Retiro confirmado en sucursal"),
    ("LLAMAR AL CLIENTE", "Sin categorizar"),
    ("CONTROLAR", "Sin categorizar"),                              # has CON but no order reference
])
def test_incident_category(note, expected):
    assert incident_category(note) == expected

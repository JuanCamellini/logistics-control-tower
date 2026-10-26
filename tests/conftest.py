from datetime import date

import pandas as pd
import pytest

from lct import config as cfg
from lct.rules import refresh_calculated_columns
from lct.warehouse import build_warehouse, connect

AS_OF = date(2026, 6, 30)  # a Tuesday

CUSTOMERS = {
    "EXPRESO DELTA": (100001, "LIBRERIA EL FARO S.A.", "MITRE 1200", "CIUDAD AUTONOMA DE BUENOS AIRES",
                      "Capital Federal", "LGAR-Capital-Oeste 1"),
    "LOGISTICA SUR": (100002, "PAPELERA ATLANTICA", "AV. COLON 800", "MAR DEL PLATA", "Buenos Aires",
                      "LGAR-Bs.As. Costa-MAREA"),
    "TRANSPORTES ANDINOS": (100003, "LIBROS LOS ANDES S.R.L.", "BELGRANO 455", "CORDOBA", "Córdoba",
                            "LGAR-Int-Andinos-Suc-Cordoba"),
}


def tiny_master() -> pd.DataFrame:
    """Eight hand-made orders. Every calculated value is worked out in the comments (as of 2026-06-30)."""
    rows = [
        # order, carrier, document date, status, pick-up, arrival, packages, note, mail already sent
        (1, "EXPRESO DELTA", "2026-06-26", "EN GESTION", None, None, 2, None, False),        # sent 29/06: 1 bd, SLA 2 -> not critical
        (2, "EXPRESO DELTA", "2026-06-24", "EN GESTION", None, None, 3, None, False),        # sent 25/06: 3 bd -> critical, not notified yet
        (3, "EXPRESO DELTA", "2026-06-22", "EN GESTION", None, None, 4, None, True),         # 5 bd -> critical, already notified
        (4, "TRANSPORTES ANDINOS", "2026-06-01", "RETIRADO", "2026-06-08", None, 10, None, False),  # 16 bd since pick-up, reaches SLA 15 -> critical
        (5, "TRANSPORTES ANDINOS", "2026-06-16", "EN GESTION", None, None, 6, None, False),  # sent 17/06: 9 bd, SLA 10 -> not critical
        (6, "LOGISTICA SUR", "2026-06-01", "EN PUNTO DE CONTROL", "2026-06-05", "2026-06-12", 1, None, False),  # cycle: 11 days
        (7, "EXPRESO DELTA", "2026-06-03", "DEPURADA", None, None, 5, "RETIRADA CON ORDEN 26100002", False),
        (8, "EXPRESO DELTA", "2026-05-04", "EN PUNTO DE CONTROL", "2026-05-07", "2026-05-14", 7, None, False),  # cycle: 10 days
    ]
    records = []
    for order, carrier, doc, status, pickup, arrival, packages, note, mail in rows:
        number, name, street, locality, province, route_code = CUSTOMERS[carrier]
        records.append({
            "Documento de ventas": 26100000 + order, "Solicitante": number, "Nombre": name, "Calle": street,
            "Población": locality, "Denominación": province, "Denominación2": route_code, "PROVEEDOR": carrier,
            "Fecha documento": pd.Timestamp(doc), "FECHA DE ENVIO": pd.NaT, "DIAS DE ATRASO": None,
            "Cantidad de pedido": packages, "ESTADO": status, "FECHA PROBABLE DE RETIRO": pd.NaT,
            "FECHA EXACTA DE RETIRO": pd.Timestamp(pickup) if pickup else pd.NaT,
            "FECHA PROBABLE DE LLEGADA A DC": pd.NaT,
            "FECHA EXACTA DE LLEGADA A DC": pd.Timestamp(arrival) if arrival else pd.NaT,
            "Observacion": note, "Dias Habiles Transcurridos": None, "Es Critica": False, "Mail": mail,
        })
    master = pd.DataFrame(records)[cfg.MASTER_COLUMNS]
    return refresh_calculated_columns(master, AS_OF)


@pytest.fixture
def master():
    return tiny_master()


@pytest.fixture
def warehouse(master, tmp_path):
    db_path = tmp_path / "test.duckdb"
    build_warehouse(master, AS_OF, db_path)
    con = connect(db_path)
    yield con
    con.close()

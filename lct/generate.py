"""Generates a fictional master Excel of pick-up orders.

Customers, addresses, carriers and the depot are invented. Monthly volume, carrier split
and SLA thresholds follow the real operation the project is modelled on.
"""
from __future__ import annotations

from datetime import date
from pathlib import Path

import numpy as np
import pandas as pd

from . import config as cfg
from .rules import critical_since, refresh_calculated_columns, sent_date

CUSTOMERS_PER_REGION = {"AMBA": 90, "COSTA": 15, "INTERIOR": 55}

# (province, locality, route code) by region
LOCATIONS = {
    "AMBA": [
        ("Capital Federal", "CIUDAD AUTONOMA DE BUENOS AIRES", "LGAR-Capital-Oeste 1"),
        ("Capital Federal", "CIUDAD AUTONOMA DE BUENOS AIRES", "LGAR-Capital-Centro 2"),
        ("Buenos Aires", "SAN ISIDRO", "LGAR-GBA-Norte 1"),
        ("Buenos Aires", "PILAR", "LGAR-GBA-Norte 2"),
        ("Buenos Aires", "LOMAS DE ZAMORA", "LGAR-GBA-Sur 1"),
        ("Buenos Aires", "QUILMES", "LGAR-GBA-Sur 1"),
        ("Buenos Aires", "MORON", "LGAR-GBA-Oeste 1"),
    ],
    "COSTA": [
        ("Buenos Aires", "MAR DEL PLATA", "LGAR-Bs.As. Costa-MAREA"),
        ("Buenos Aires", "PINAMAR", "LGAR-Bs.As. Costa-FARO"),
        ("Buenos Aires", "VILLA GESELL", "LGAR-Bs.As. Costa-FARO"),
        ("Buenos Aires", "NECOCHEA", "LGAR-Bs.As. Costa-MAREA"),
    ],
    "INTERIOR": [
        ("Córdoba", "CORDOBA", "LGAR-Int-Andinos-Suc-Cordoba"),
        ("Córdoba", "RIO CUARTO", "LGAR-Int-Andinos-Suc-Cordoba"),
        ("Santa Fe", "ROSARIO", "LGAR-Int-Andinos-Suc-Rosario"),
        ("Mendoza", "MENDOZA", "LGAR-Int-Andinos-Suc-Mendoza"),
        ("Tucumán", "SAN MIGUEL DE TUCUMAN", "LGAR-Int-Andinos-Suc-Tucuman"),
        ("Salta", "SALTA", "LGAR-Int-Andinos-Suc-Salta"),
        ("Tierra del Fuego", "USHUAIA", "LGAR-Int-Andinos-Suc-Ushuaia"),
        ("Neuquén", "NEUQUEN", "LGAR-Int-Andinos-Suc-Neuquen"),
        ("Corrientes", "CORRIENTES", "LGAR-Int-Andinos-Suc-Corrientes"),
    ],
}

NAME_PREFIXES = ["LIBRERIA", "DISTRIBUIDORA", "PAPELERA", "LIBROS", "CADENA"]
NAME_CORES = ["EL FARO", "DEL CENTRO", "LA ESTACION", "LOS ANDES", "DEL PUERTO", "ATLANTICA", "PATAGONIA",
              "SAN MARTIN", "EL ALJIBE", "LA PLAZA", "DEL SUR", "MERIDIANO", "EL ATENEO NUEVO", "LA RUEDA"]
NAME_SUFFIXES = ["S.A.", "S.R.L.", "", "S.A.S."]
STREETS = ["AV. SAN MARTIN", "BELGRANO", "RIVADAVIA", "MITRE", "SARMIENTO", "AV. COLON", "9 DE JULIO",
           "MORENO", "ITALIA", "INDEPENDENCIA", "LAPRIDA", "AV. LIBERTADOR"]

# Notes for purged orders: (template, weight). {n} becomes another order number.
PURGE_NOTES = [
    ("RETIRADA CON ORDEN {n}", 0.30), ("RENDIDA CON OR {n}", 0.20), ("DUPLICADA {n}", 0.07),
    ("SE REPITE CON {n}", 0.03), ("RETIRO FALLIDO, NO HABIA MERCADERIA", 0.05), ("NADA PARA RETIRAR", 0.05),
    ("", 0.10), ("EL CLIENTE DIO DE BAJA EL PEDIDO", 0.04), ("ELIMINADA A PEDIDO DE COMERCIAL", 0.03),
    ("LOCAL CERRADO", 0.05), ("CANTIDAD DIFIERE DE LO INFORMADO", 0.03), ("LA TRAE EL CLIENTE AL DEPOSITO", 0.02),
    ("MERCADERIA DEVUELTA AL CLIENTE", 0.02), ("SE GENERO NUEVA ORDEN {n}", 0.01),
]
# Occasional notes on orders that are not purged
OPEN_NOTES = [("ESPERA DE INFORMACION DEL PROVEEDOR", 0.4), ("CLIENTE DE VACACIONES", 0.2),
              ("MERCADERIA EN SUCURSAL", 0.2), ("RETIRO REALIZADO, FALTA RENDIR", 0.1), ("DOCUMENTACION EN ADUANA", 0.1)]
OPEN_NOTE_RATE = 0.06


def _pick(rng, options, size):
    texts, weights = zip(*options)
    weights = np.array(weights) / sum(weights)
    return rng.choice(texts, size=size, p=weights)


def build_customers(rng: np.random.Generator) -> pd.DataFrame:
    rows, number = [], 100001
    carrier_by_region = {c.region: c for c in cfg.CARRIERS}
    for region, count in CUSTOMERS_PER_REGION.items():
        for _ in range(count):
            province, locality, route_code = LOCATIONS[region][rng.integers(len(LOCATIONS[region]))]
            name = " ".join(filter(None, [rng.choice(NAME_PREFIXES), rng.choice(NAME_CORES), rng.choice(NAME_SUFFIXES)]))
            rows.append({
                "Solicitante": number,
                "Nombre": name,
                "Calle": f"{rng.choice(STREETS)} {rng.integers(100, 4000)}",
                "Población": locality,
                "Denominación": province,
                "Denominación2": route_code,
                "PROVEEDOR": carrier_by_region[region].name,
            })
            number += 1
    return pd.DataFrame(rows)


def build_master(seed: int = cfg.SEED, start: date = cfg.START_DATE, as_of: date = cfg.AS_OF_DATE) -> pd.DataFrame:
    """Every order created between start and as_of, in its state as of that day."""
    rng = np.random.default_rng(seed)
    customers = build_customers(rng)

    days = np.arange(np.datetime64(start, "D"), np.datetime64(as_of, "D") + np.timedelta64(1, "D"))
    days = days[np.is_busday(days)]
    orders_per_day = cfg.ORDERS_PER_MONTH * 12 / 261
    document_date = np.repeat(days, rng.poisson(orders_per_day, size=len(days)))
    n = len(document_date)

    carriers = list(cfg.CARRIERS)
    volume = np.array([c.orders_per_month for c in carriers], dtype=float)
    carrier_idx = rng.choice(len(carriers), size=n, p=volume / volume.sum())
    pickup_mean = np.array([carriers[i].pickup_delay_mean for i in carrier_idx])
    depot_mean = np.array([carriers[i].depot_delay_mean for i in carrier_idx])
    pickup_sla = np.array([carriers[i].pickup_sla_days for i in carrier_idx])
    depot_sla = np.array([carriers[i].depot_sla_days for i in carrier_idx])
    packages_mean = np.array([carriers[i].packages_mean for i in carrier_idx])

    # Each order goes to a random customer served by its carrier
    customer_rows = np.empty(n, dtype=int)
    for i, carrier in enumerate(carriers):
        mask = carrier_idx == i
        candidates = np.flatnonzero(customers["PROVEEDOR"].to_numpy() == carrier.name)
        customer_rows[mask] = rng.choice(candidates, size=int(mask.sum()))
    df = customers.iloc[customer_rows].reset_index(drop=True)

    sent = sent_date(document_date)
    pickup_days = 1 + rng.poisson(pickup_mean) + np.where(rng.random(n) < cfg.STUCK_PICKUP_RATE, rng.integers(15, 80, n), 0)
    depot_days = 1 + rng.poisson(depot_mean) + np.where(rng.random(n) < cfg.STUCK_DEPOT_RATE, rng.integers(10, 50, n), 0)
    pickup = np.busday_offset(sent, pickup_days)
    arrival = np.busday_offset(pickup, depot_days)

    as_of64 = np.datetime64(as_of, "D")
    status = np.where(pickup > as_of64, cfg.IN_PROGRESS, np.where(arrival > as_of64, cfg.PICKED_UP, cfg.AT_DEPOT))
    u = rng.random(n)
    status = np.where(u < cfg.PURGED_RATE, cfg.PURGED, np.where(u < cfg.PURGED_RATE + cfg.TO_PURGE_RATE, cfg.TO_PURGE, status))

    nat = np.datetime64("NaT", "D")
    has_pickup = np.isin(status, [cfg.PICKED_UP, cfg.AT_DEPOT])
    has_arrival = status == cfg.AT_DEPOT

    order_numbers = np.arange(26100001, 26100001 + n)
    notes = np.where(rng.random(n) < OPEN_NOTE_RATE, _pick(rng, OPEN_NOTES, n), "")
    purge_notes = _pick(rng, PURGE_NOTES, n)
    other_order = rng.integers(26100001, 26100001 + n, size=n)
    purge_notes = np.array([t.format(n=o) for t, o in zip(purge_notes, other_order)])
    notes = np.where(status == cfg.PURGED, purge_notes, notes)
    notes = np.where(status == cfg.TO_PURGE, ["A DEPURAR - DUPLICADA " + str(o) for o in other_order], notes)

    df.insert(0, "Documento de ventas", order_numbers)
    df["Fecha documento"] = pd.to_datetime(document_date)
    df["Cantidad de pedido"] = 1 + rng.poisson(packages_mean)
    df["ESTADO"] = status
    df["FECHA PROBABLE DE RETIRO"] = pd.to_datetime(np.busday_offset(sent, pickup_sla))
    df["FECHA EXACTA DE RETIRO"] = pd.to_datetime(np.where(has_pickup, pickup, nat))
    expected_from = np.where(has_pickup, pickup, np.busday_offset(sent, pickup_sla))
    df["FECHA PROBABLE DE LLEGADA A DC"] = pd.to_datetime(np.busday_offset(expected_from, depot_sla))
    df["FECHA EXACTA DE LLEGADA A DC"] = pd.to_datetime(np.where(has_arrival, arrival, nat))
    df["Observacion"] = np.where(notes == "", None, notes)

    df = refresh_calculated_columns(df, as_of)
    # The alert ran every day up to yesterday: orders that were already critical before today were notified.
    df["Mail"] = df["Es Critica"] & (critical_since(df) < as_of64)
    return df[cfg.MASTER_COLUMNS]


def write_master(df: pd.DataFrame, path: Path = cfg.MASTER_PATH) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with pd.ExcelWriter(path, engine="openpyxl", date_format="DD/MM/YYYY", datetime_format="DD/MM/YYYY") as writer:
        df[cfg.MASTER_COLUMNS].to_excel(writer, sheet_name=cfg.MASTER_SHEET, index=False)


def read_master(path: Path = cfg.MASTER_PATH) -> pd.DataFrame:
    df = pd.read_excel(path, sheet_name=cfg.MASTER_SHEET, engine="openpyxl")
    for col in cfg.DATE_COLUMNS:
        df[col] = pd.to_datetime(df[col])
    df["Mail"] = df["Mail"].fillna(False).astype(bool)
    return df

"""Business rules of the pick-up order process.

Each rule is a small function so it can be tested on its own. Business days skip
weekends only; public holidays are not taken into account.
"""
from __future__ import annotations

import re
from datetime import date

import numpy as np
import pandas as pd

from . import config as cfg

CARRIER_BY_NAME = {c.name: c for c in cfg.CARRIERS}


def _days(values) -> np.ndarray:
    return pd.to_datetime(pd.Series(values)).to_numpy(dtype="datetime64[D]")


def business_days_between(start, end) -> np.ndarray:
    """Business days from start (included) to end (excluded). NaN when either date is missing."""
    start, end = _days(start), _days(end)
    out = np.full(len(start), np.nan)
    known = ~(np.isnat(start) | np.isnat(end))
    out[known] = np.busday_count(start[known], end[known])
    return out


def sent_date(document_date) -> np.ndarray:
    """Orders are sent to the carrier one business day after the document is created."""
    return np.busday_offset(_days(document_date), 1, roll="forward")


def business_days_in_status(df: pd.DataFrame, as_of: date) -> np.ndarray:
    """Business days the order has spent in its current pending status.

    EN GESTION counts from the sent date, RETIRADO from the pick-up date. Other statuses: NaN.
    """
    as_of_col = [as_of] * len(df)
    from_sent = business_days_between(df["FECHA DE ENVIO"], as_of_col)
    from_pickup = business_days_between(df["FECHA EXACTA DE RETIRO"], as_of_col)
    status = df["ESTADO"].to_numpy()
    return np.select([status == cfg.IN_PROGRESS, status == cfg.PICKED_UP], [from_sent, from_pickup], default=np.nan)


def is_critical(df: pd.DataFrame, business_days: np.ndarray) -> np.ndarray:
    """Critical: the business days in a pending status reach the carrier's SLA for that step."""
    carriers = df["PROVEEDOR"].map(CARRIER_BY_NAME)
    pickup_sla = carriers.map(lambda c: c.pickup_sla_days).to_numpy(dtype=float)
    depot_sla = carriers.map(lambda c: c.depot_sla_days).to_numpy(dtype=float)
    status = df["ESTADO"].to_numpy()
    with np.errstate(invalid="ignore"):
        return ((status == cfg.IN_PROGRESS) & (business_days >= pickup_sla)) | (
            (status == cfg.PICKED_UP) & (business_days >= depot_sla)
        )


def delay_days(df: pd.DataFrame, as_of: date) -> np.ndarray:
    """Calendar days from document creation until the order reaches the depot (or until as_of).

    Purged orders (DEPURADA) have no delay.
    """
    end = df["FECHA EXACTA DE LLEGADA A DC"].fillna(pd.Timestamp(as_of))
    days = (pd.to_datetime(end) - pd.to_datetime(df["Fecha documento"])).dt.days.astype(float).to_numpy()
    return np.where(df["ESTADO"].to_numpy() == cfg.PURGED, np.nan, days)


def delay_bucket(days) -> list:
    """Groups the delay days into the dashboard ranges."""
    def bucket(d):
        if pd.isna(d):
            return None
        if d <= 7:
            return "0 - 7 días"
        if d <= 15:
            return "8 - 15 días"
        if d <= 30:
            return "16 - 30 días"
        if d <= 60:
            return "31 - 60 días"
        return "> 60 días"
    return [bucket(d) for d in days]


def route(route_code) -> str | None:
    """Route group from the shipping route code (column Denominación2)."""
    if route_code is None or pd.isna(route_code):
        return None
    code = str(route_code).lower()
    for keyword, name in (("int", "Interior"), ("costa", "Costa Atlántica"), ("gba", "GBA"), ("capital", "CABA")):
        if keyword in code:
            return name
    return None


def incident_category(note) -> str:
    """Incident category from the free-text note (column Observacion). Rules are checked in order."""
    text = "" if note is None or pd.isna(note) else str(note).strip().upper()
    if text == "":
        return "Sin observación"

    def has(*words):
        return any(w in text for w in words)

    if has("DUPLICA", "REPITE"):
        return "Duplicada / Repetida"
    if has("DIFIERE"):
        return "Diferencia de cantidad"
    if has("RETIRO FALLIDO", "NADA PARA RETIRAR"):
        return "Retiro fallido / sin mercadería"
    if has("DIO DE BAJA", "ELIMINADA"):
        return "Baja del cliente"
    if has("CERRAD"):
        return "Cliente / local cerrado"
    if has("TRAE EL CLIENTE"):
        return "Cliente entrega directo"
    if has("ENTREGADO AL CLIENTE", "ENTREGADA AL CLIENTE", "DEVUEL"):
        return "Retirada, devuelta al cliente"
    if has("CON") and (has("ORDEN", " OR ") or re.search(r"\d", text)):
        return "Retirada / rendida con otra orden"
    if has("SE GENERO"):
        return "Nueva orden generada"
    if has("ESPERA DE INFORMACI"):
        return "Espera de información del proveedor"
    if has("VACACIONES"):
        return "Cliente no disponible (temporal)"
    if has("ADUANA"):
        return "Documentación / Aduana"
    if has("MERCADERIA EN SUCURSAL", "RETIRO REALIZADO"):
        return "Retiro confirmado en sucursal"
    return "Sin categorizar"


def critical_since(df: pd.DataFrame) -> np.ndarray:
    """First day on which each pending order counts as critical (NaT for other statuses)."""
    carriers = df["PROVEEDOR"].map(CARRIER_BY_NAME)
    status = df["ESTADO"].to_numpy()
    out = np.full(len(df), np.datetime64("NaT", "D"), dtype="datetime64[D]")
    for state, start_col, sla_attr in (
        (cfg.IN_PROGRESS, "FECHA DE ENVIO", "pickup_sla_days"),
        (cfg.PICKED_UP, "FECHA EXACTA DE RETIRO", "depot_sla_days"),
    ):
        mask = (status == state) & df[start_col].notna().to_numpy()
        if mask.any():
            sla = carriers[mask].map(lambda c: getattr(c, sla_attr)).to_numpy(dtype=int)
            out[mask] = np.busday_offset(_days(df.loc[mask, start_col]), sla, roll="forward")
    return out


def leg_sla_status(df: pd.DataFrame, as_of: date) -> pd.DataFrame:
    """Business days and SLA status of each leg: sent -> pick-up, and pick-up -> depot.

    A leg still open is measured until as_of. Status: "En plazo", "Fuera de plazo" or "En curso".
    """
    carriers = df["PROVEEDOR"].map(CARRIER_BY_NAME)
    status = df["ESTADO"].to_numpy()
    as_of_ts = pd.Timestamp(as_of)
    measured = ~np.isin(status, [cfg.PURGED, cfg.TO_PURGE])

    pickup_end = df["FECHA EXACTA DE RETIRO"].where(df["FECHA EXACTA DE RETIRO"].notna(), as_of_ts)
    pickup_days = np.where(measured, business_days_between(df["FECHA DE ENVIO"], pickup_end), np.nan)
    depot_days = np.where(
        measured,
        business_days_between(df["FECHA EXACTA DE RETIRO"],
                              df["FECHA EXACTA DE LLEGADA A DC"].where(df["FECHA EXACTA DE LLEGADA A DC"].notna(), as_of_ts)),
        np.nan,
    )

    def label(days, sla, finished):
        out = np.full(len(days), None, dtype=object)
        known = ~np.isnan(days)
        out[known & ~finished] = "En curso"
        out[known & finished] = "En plazo"
        out[known & (days >= sla)] = "Fuera de plazo"
        return out

    with np.errstate(invalid="ignore"):
        pickup_status = label(pickup_days, carriers.map(lambda c: c.pickup_sla_days).to_numpy(float),
                              df["FECHA EXACTA DE RETIRO"].notna().to_numpy())
        depot_status = label(depot_days, carriers.map(lambda c: c.depot_sla_days).to_numpy(float),
                             df["FECHA EXACTA DE LLEGADA A DC"].notna().to_numpy())
    return pd.DataFrame({
        "pickup_business_days": pickup_days,
        "pickup_sla_status": pickup_status,
        "depot_business_days": depot_days,
        "depot_sla_status": depot_status,
    }, index=df.index)


def refresh_calculated_columns(master: pd.DataFrame, as_of: date) -> pd.DataFrame:
    """Recalculates the master's computed columns, as the Excel formulas would on that day."""
    df = master.copy()
    df["FECHA DE ENVIO"] = pd.to_datetime(sent_date(df["Fecha documento"]))
    df["DIAS DE ATRASO"] = delay_days(df, as_of)
    df["Dias Habiles Transcurridos"] = business_days_in_status(df, as_of)
    df["Es Critica"] = is_critical(df, df["Dias Habiles Transcurridos"].to_numpy())
    return df


def add_analysis_columns(df: pd.DataFrame) -> pd.DataFrame:
    """Columns derived for the dashboard only (not part of the master Excel)."""
    out = df.copy()
    out["Ruta"] = [route(c) for c in out["Denominación2"]]
    out["Categoria de Incidencia"] = [incident_category(n) for n in out["Observacion"]]
    out["Rango Atraso"] = delay_bucket(out["DIAS DE ATRASO"])
    return out

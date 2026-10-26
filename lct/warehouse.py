"""Loads the master Excel into a DuckDB star schema and runs the SQL files."""
from __future__ import annotations

from datetime import date, timedelta
from pathlib import Path

import duckdb
import pandas as pd

from . import config as cfg
from .rules import add_analysis_columns, leg_sla_status, refresh_calculated_columns

TABLES = ["dim_carrier", "dim_customer", "dim_date", "meta_snapshot", "fact_pickup_order"]


def read_sql(relative_path: str) -> str:
    return (cfg.SQL_DIR / relative_path).read_text(encoding="utf-8")


def model_tables(master: pd.DataFrame, as_of: date) -> dict[str, pd.DataFrame]:
    """Turns the master Excel into the tables of the star schema."""
    df = add_analysis_columns(refresh_calculated_columns(master, as_of))
    carrier_id = {c.name: c.carrier_id for c in cfg.CARRIERS}

    carriers = pd.DataFrame(
        {"carrier_id": c.carrier_id, "carrier_name": c.name,
         "pickup_sla_days": c.pickup_sla_days, "depot_sla_days": c.depot_sla_days}
        for c in cfg.CARRIERS
    )
    customers = (
        df.drop_duplicates("Solicitante")
        .rename(columns={"Solicitante": "customer_id", "Nombre": "customer_name", "Calle": "street",
                         "Población": "locality", "Denominación": "province", "Denominación2": "route_code",
                         "Ruta": "route"})
        [["customer_id", "customer_name", "street", "locality", "province", "route_code", "route"]]
    )
    days = pd.date_range(df["Fecha documento"].min(), as_of + timedelta(days=60), freq="D")
    calendar = pd.DataFrame({"date_key": days, "year": days.year, "month": days.month,
                             "month_name": days.strftime("%b"), "is_business_day": days.dayofweek < 5})
    facts = pd.DataFrame({
        "order_id": df["Documento de ventas"],
        "customer_id": df["Solicitante"],
        "carrier_id": df["PROVEEDOR"].map(carrier_id),
        "document_date": df["Fecha documento"],
        "sent_date": df["FECHA DE ENVIO"],
        "expected_pickup_date": df["FECHA PROBABLE DE RETIRO"],
        "pickup_date": df["FECHA EXACTA DE RETIRO"],
        "expected_arrival_date": df["FECHA PROBABLE DE LLEGADA A DC"],
        "arrival_date": df["FECHA EXACTA DE LLEGADA A DC"],
        "packages": df["Cantidad de pedido"],
        "status": df["ESTADO"],
        "is_critical": df["Es Critica"].astype(bool),
        "alert_sent": df["Mail"].astype(bool),
        "delay_days": df["DIAS DE ATRASO"].astype("Int64"),
        "delay_bucket": df["Rango Atraso"],
        "business_days_in_status": df["Dias Habiles Transcurridos"].astype("Int64"),
        "notes": df["Observacion"],
        "incident_category": df["Categoria de Incidencia"],
    })
    legs = leg_sla_status(df, as_of)
    facts["pickup_business_days"] = legs["pickup_business_days"].astype("Int64")
    facts["pickup_sla_status"] = legs["pickup_sla_status"]
    facts["depot_business_days"] = legs["depot_business_days"].astype("Int64")
    facts["depot_sla_status"] = legs["depot_sla_status"]
    return {
        "dim_carrier": carriers,
        "dim_customer": customers,
        "dim_date": calendar,
        "meta_snapshot": pd.DataFrame({"as_of_date": [pd.Timestamp(as_of)]}),
        "fact_pickup_order": facts,
    }


def build_warehouse(master: pd.DataFrame, as_of: date, db_path: Path = cfg.WAREHOUSE_PATH) -> None:
    """Recreates the warehouse from scratch with the current state of the master."""
    db_path.parent.mkdir(parents=True, exist_ok=True)
    db_path.unlink(missing_ok=True)
    tables = model_tables(master, as_of)
    with duckdb.connect(str(db_path)) as con:
        con.execute(read_sql("schema.sql"))
        for name in TABLES:
            con.register("staging", tables[name])
            con.execute(f"INSERT INTO {name} BY NAME SELECT * FROM staging")
            con.unregister("staging")


def connect(db_path: Path = cfg.WAREHOUSE_PATH) -> duckdb.DuckDBPyConnection:
    return duckdb.connect(str(db_path))


def run_sql_file(con: duckdb.DuckDBPyConnection, relative_path: str) -> pd.DataFrame:
    return con.execute(read_sql(relative_path)).df()


def run_kpis(con: duckdb.DuckDBPyConnection, out_dir: Path) -> dict[str, pd.DataFrame]:
    """Runs every query in sql/kpis and saves each result as a CSV."""
    out_dir.mkdir(parents=True, exist_ok=True)
    results = {}
    for path in sorted((cfg.SQL_DIR / "kpis").glob("*.sql")):
        df = run_sql_file(con, f"kpis/{path.name}")
        df.to_csv(out_dir / f"{path.stem}.csv", index=False)
        results[path.stem] = df
    return results


def export_for_powerbi(con: duckdb.DuckDBPyConnection, out_dir: Path) -> None:
    """One CSV per table, read by the Power BI project."""
    out_dir.mkdir(parents=True, exist_ok=True)
    for table in TABLES:
        path = (out_dir / f"{table}.csv").as_posix()
        con.execute(f"COPY {table} TO '{path}' (HEADER, DELIMITER ',')")

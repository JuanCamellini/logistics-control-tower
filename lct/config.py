"""Project settings: paths, simulation window and the (fictional) carriers with their SLAs."""
from __future__ import annotations

from dataclasses import dataclass
from datetime import date
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
DATA_DIR = ROOT / "data"
MASTER_PATH = DATA_DIR / "maestro_ordenes_retiro.xlsx"   # the master Excel the operation works on
MASTER_SHEET = "Ordenes"
OUTPUT_DIR = ROOT / "output"
SQL_DIR = ROOT / "sql"
WAREHOUSE_PATH = OUTPUT_DIR / "warehouse.duckdb"

SEED = 42
START_DATE = date(2026, 1, 2)
AS_OF_DATE = date(2026, 8, 31)     # "today" for the snapshot: pending days and alerts are measured on it
ORDERS_PER_MONTH = 230
N_CUSTOMERS = 160

# Share of orders that get stuck (extra business days before pick-up / before reaching the depot)
STUCK_PICKUP_RATE = 0.04
STUCK_DEPOT_RATE = 0.02
PURGED_RATE = 0.05        # DEPURADA
TO_PURGE_RATE = 0.004     # DEPURAR: flagged, not purged yet


@dataclass(frozen=True)
class Carrier:
    carrier_id: str
    name: str                  # as it appears in the PROVEEDOR column
    pickup_sla_days: int       # business days from sent date to pick-up; reaching it = critical
    depot_sla_days: int        # business days from pick-up to arrival at the depot; reaching it = critical
    orders_per_month: int
    pickup_delay_mean: float   # simulation: pick-up happens 1 + Poisson(mean) business days after sending
    depot_delay_mean: float    # simulation: arrival happens 1 + Poisson(mean) business days after pick-up
    packages_mean: float
    region: str                # AMBA, COSTA or INTERIOR: drives the customers it serves


# Fictional carriers. SLA thresholds and monthly volumes follow the real operation.
CARRIERS = (
    Carrier("EXD", "EXPRESO DELTA", 2, 3, 160, 1.2, 1.8, 3.5, "AMBA"),
    Carrier("LSU", "LOGISTICA SUR", 5, 7, 10, 3.5, 5.0, 2.0, "COSTA"),
    Carrier("TAN", "TRANSPORTES ANDINOS", 10, 15, 60, 7.0, 10.0, 8.0, "INTERIOR"),
)

# Status values in the ESTADO column
IN_PROGRESS = "EN GESTION"
PICKED_UP = "RETIRADO"
AT_DEPOT = "EN PUNTO DE CONTROL"
PURGED = "DEPURADA"
TO_PURGE = "DEPURAR"
PENDING_STATUSES = (IN_PROGRESS, PICKED_UP)

# Columns of the master Excel, in order
MASTER_COLUMNS = [
    "Documento de ventas", "Solicitante", "Nombre", "Calle", "Población", "Denominación", "Denominación2",
    "PROVEEDOR", "Fecha documento", "FECHA DE ENVIO", "DIAS DE ATRASO", "Cantidad de pedido", "ESTADO",
    "FECHA PROBABLE DE RETIRO", "FECHA EXACTA DE RETIRO", "FECHA PROBABLE DE LLEGADA A DC",
    "FECHA EXACTA DE LLEGADA A DC", "Observacion", "Dias Habiles Transcurridos", "Es Critica", "Mail",
]
DATE_COLUMNS = [
    "Fecha documento", "FECHA DE ENVIO", "FECHA PROBABLE DE RETIRO", "FECHA EXACTA DE RETIRO",
    "FECHA PROBABLE DE LLEGADA A DC", "FECHA EXACTA DE LLEGADA A DC",
]

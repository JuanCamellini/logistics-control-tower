"""KPI queries checked against the eight hand-made orders in conftest.py."""
import pytest

from lct.warehouse import run_sql_file


def kpi(con, name):
    return run_sql_file(con, f"kpis/{name}.sql")


def test_kpi_cards(warehouse):
    cards = kpi(warehouse, "01_kpi_cards").iloc[0]
    assert cards["total_orders"] == 8
    assert cards["total_packages"] == 38
    assert cards["in_progress_orders"] == 4 and cards["in_progress_packages"] == 15   # orders 1, 2, 3, 5
    assert cards["picked_up_orders"] == 1 and cards["picked_up_packages"] == 10      # order 4
    assert cards["critical_orders"] == 3 and cards["critical_packages"] == 17        # orders 2, 3, 4
    assert cards["critical_rate"] == pytest.approx(0.6)                               # 3 of 5 pending
    assert cards["purged_rate"] == pytest.approx(0.125)                               # 1 of 8
    assert cards["avg_cycle_days"] == pytest.approx(10.5)                             # orders 6 and 8


def test_orders_by_status(warehouse):
    by_status = kpi(warehouse, "02_orders_by_status").set_index("status")["orders"].to_dict()
    assert by_status == {"EN GESTION": 4, "EN PUNTO DE CONTROL": 2, "RETIRADO": 1, "DEPURADA": 1}


def test_pending_by_carrier(warehouse):
    pending = kpi(warehouse, "03_pending_by_carrier").set_index("carrier_name")
    assert pending.loc["EXPRESO DELTA", "pending_orders"] == 3
    assert pending.loc["EXPRESO DELTA", "critical_orders"] == 2
    assert pending.loc["TRANSPORTES ANDINOS", "pending_packages"] == 16
    assert pending.loc["LOGISTICA SUR", "pending_orders"] == 0     # carriers with nothing pending still show up


def test_pending_aging(warehouse):
    aging = kpi(warehouse, "04_pending_aging").set_index("delay_bucket")
    assert aging.index.tolist() == ["0 - 7 días", "8 - 15 días", "16 - 30 días"]
    assert aging.loc["0 - 7 días", "in_progress_orders"] == 2        # orders 1 and 2
    assert aging.loc["8 - 15 días", "pending_orders"] == 2           # orders 3 and 5
    assert aging.loc["16 - 30 días", "picked_up_orders"] == 1        # order 4


def test_purge_reasons(warehouse):
    reasons = kpi(warehouse, "05_purge_reasons")
    assert reasons.to_dict("records") == [{"incident_category": "Retirada / rendida con otra orden", "orders": 1}]


def test_province_and_delay_views_run(warehouse):
    assert kpi(warehouse, "06_avg_delay_by_carrier")["orders"].sum() == 5
    assert kpi(warehouse, "07_pending_packages_by_province")["pending_packages"].sum() == 25   # 9 in CABA + 16 in Córdoba

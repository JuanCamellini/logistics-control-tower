"""Command line entry point: python -m lct [step]"""
from __future__ import annotations

import argparse

from . import config as cfg
from .alerts import run_alerts
from .generate import build_master, read_master, write_master
from .rules import refresh_calculated_columns
from .warehouse import build_warehouse, connect, export_for_powerbi, run_kpis

STEPS = ["generate", "alerts", "build", "kpis", "export"]


def main(argv: list[str] | None = None) -> None:
    parser = argparse.ArgumentParser(prog="python -m lct", description="Pick-up order traceability on fictional data.")
    parser.add_argument("step", nargs="?", default="all", choices=STEPS + ["all"],
                        help="pipeline step to run (default: all)")
    step = parser.parse_args(argv).step
    steps = STEPS if step == "all" else [step]
    as_of = cfg.AS_OF_DATE

    if "generate" in steps:
        master = build_master()
        write_master(master)
        print(f"Master Excel with {len(master):,} pick-up orders -> {cfg.MASTER_PATH}")

    if "alerts" in steps:
        updated, summary = run_alerts(read_master(), as_of, cfg.OUTPUT_DIR / "alerts")
        write_master(refresh_calculated_columns(updated, as_of)[cfg.MASTER_COLUMNS])
        print(f"Alert emails: {len(summary)} carriers, {int(summary['orders'].sum())} orders notified")

    if "build" in steps:
        build_warehouse(read_master(), as_of)
        print(f"Warehouse built -> {cfg.WAREHOUSE_PATH}")

    if "kpis" in steps or "export" in steps:
        with connect() as con:
            if "kpis" in steps:
                results = run_kpis(con, cfg.OUTPUT_DIR / "kpis")
                print("\nKPI cards")
                print(results["01_kpi_cards"].T.to_string(header=False))
            if "export" in steps:
                export_for_powerbi(con, cfg.OUTPUT_DIR / "powerbi")
                print(f"\nPower BI tables -> {cfg.OUTPUT_DIR / 'powerbi'}")


if __name__ == "__main__":
    main()

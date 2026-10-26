"""Daily alert: one email per carrier with its newly critical pick-up orders.

An order is included when it is critical and has not been notified yet (Mail = FALSE).
After the emails are written, those orders are marked Mail = TRUE in the master Excel,
so the next day's run does not repeat them. Emails are saved as HTML files; nothing is sent.
The text is in Spanish, like the operation it models.
"""
from __future__ import annotations

from datetime import date
from html import escape
from pathlib import Path

import pandas as pd

from . import config as cfg
from .rules import refresh_calculated_columns

EMAIL_COLUMNS = {
    "Documento de ventas": "N° de orden",
    "Nombre": "Cliente",
    "Calle": "Dirección",
    "Población": "Localidad",
    "Cantidad de pedido": "Bultos",
    "FECHA DE ENVIO": "Fecha de envío",
    "Dias Habiles Transcurridos": "Días hábiles transcurridos",
    "Observacion": "Observaciones",
}

EMAIL_TEMPLATE = """<html><body style="font-family: Arial, sans-serif; font-size: 14px;">
<p>Hola, equipo de {carrier}:</p>
<p>Al {as_of} las siguientes {count} órdenes de retiro superaron el plazo acordado
({sla_pickup} días hábiles para retirar, {sla_depot} para rendir al depósito).
Les pedimos priorizarlas y confirmarnos la fecha de gestión.</p>
{table}
<p>Saludos,<br>Control de Transporte</p>
</body></html>"""


def orders_to_notify(master: pd.DataFrame, as_of: date) -> pd.DataFrame:
    df = refresh_calculated_columns(master, as_of)
    return df[df["Es Critica"] & ~df["Mail"].astype(bool)]


def run_alerts(master: pd.DataFrame, as_of: date, out_dir: Path) -> tuple[pd.DataFrame, pd.DataFrame]:
    """Writes the emails and returns (updated master, summary per carrier)."""
    pending = orders_to_notify(master, as_of)
    out_dir.mkdir(parents=True, exist_ok=True)
    rows = []
    for carrier in cfg.CARRIERS:
        orders = pending[pending["PROVEEDOR"] == carrier.name]
        if orders.empty:
            continue
        table = orders[list(EMAIL_COLUMNS)].rename(columns=EMAIL_COLUMNS).copy()
        table["Fecha de envío"] = table["Fecha de envío"].dt.strftime("%d/%m/%Y")
        table["Días hábiles transcurridos"] = table["Días hábiles transcurridos"].astype(int)
        table["Observaciones"] = table["Observaciones"].fillna("")
        html = EMAIL_TEMPLATE.format(
            carrier=escape(carrier.name.title()),
            as_of=as_of.strftime("%d/%m/%Y"),
            count=len(orders),
            sla_pickup=carrier.pickup_sla_days,
            sla_depot=carrier.depot_sla_days,
            table=table.to_html(index=False, border=0),
        )
        email_file = out_dir / f"{as_of.isoformat()}_{carrier.carrier_id}.html"
        email_file.write_text(html, encoding="utf-8")
        rows.append({"carrier": carrier.name, "orders": len(orders), "email_file": email_file.name})

    updated = master.copy()
    updated.loc[pending.index, "Mail"] = True
    summary = pd.DataFrame(rows, columns=["carrier", "orders", "email_file"])
    summary.to_csv(out_dir / f"{as_of.isoformat()}_summary.csv", index=False)
    return updated, summary

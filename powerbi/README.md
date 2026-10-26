# Power BI dashboard

`OrdenesRetiro.pbip` is a Power BI Desktop project. The semantic model (TMDL) and the report (PBIR) are plain text files, so every measure and every visual can be reviewed in Git.

![Main page](../docs/img/01_tablero_principal.png)

## Open it

1. Run the pipeline first so the CSVs exist: `python -m lct` (they land in `output/powerbi/`).
2. Open `powerbi/OrdenesRetiro.pbip` in Power BI Desktop and click **Refresh**.
3. If your repo is not at `C:\logistics-control-tower`, change the **CarpetaDatos** parameter (*Transform data → Edit parameters*). The path must end with `\`.

## Pages

**Órdenes de Retiro** (main page)
- **Search box:** type an order number, a customer name or a customer number, and every visual filters to the matches. It is an input slicer over a `search_key` column that joins the three fields.
- **Slicers:** carrier, status, delay range, route and document date. The date slicer takes a range (*from / to*); to see a single day, enter the same date in both boxes.
- **Cards:** orders and packages (total, in progress, picked up, critical), % critical over pending orders, % purged and total cycle time.
- **Order detail table.** Selecting a row does not filter the cards. In the charts it highlights the selected order and fades the rest. It also picks the customer for the drillthrough button.
- **Fixed context:** *Atraso promedio por proveedor (total)* ignores every slicer, the search box and selections. It is the carrier benchmark. *Pendientes por proveedor* and *Bultos pendientes por provincia* ignore the search box: they keep the full picture and highlight the selected order instead.
- **"Ver detalle del cliente" button:** opens the drillthrough page for the selected customer. It stays grey until exactly one customer is in context, either from a selected row or from a search by customer number. A name search can match several customers. In Power BI Desktop, buttons need **Ctrl+click**; in the Power BI service, a normal click works.
- **Six charts:** orders by status, pending orders by carrier, age of pending orders, purge reasons, average delay by carrier (ribbon) and pending packages by province.

**Detalle por Cliente** (drillthrough)
- Use the button above, or right-click any order → *Drill through → Detalle por Cliente*. The page is filtered by customer number only.
- **Top:** the customer's record (address, locality, province, route, carrier), then cards compared with the overall average.
- **Timeline:** every order, with the SLA status of each leg in green, red or yellow.
- **Bottom:** a table of purged orders with their reason and note, and orders per month. Months without orders show as zero, so customers with few orders still read well.

![Customer drillthrough](../docs/img/03_detalle_cliente.png)

![Purged orders and orders per month](../docs/img/04_detalle_depuradas_mes.png)

## Model

| Table | Content |
|---|---|
| `fact_pickup_order` | One row per pick-up order, plus every DAX measure and the `search_key` column |
| `dim_customer` | Customer, address, province and route |
| `dim_carrier` | Carrier and its SLA thresholds |
| `dim_date` | Calendar, related to the document date |
| `meta_snapshot` | Snapshot date shown as "Actualizado" |

The business rules are computed in Python and tested: critical orders, delay days, routes, incident categories and the SLA status of each leg. Power BI only aggregates them, so the dashboard and the alert emails always agree.

DAX notes:
- **`KEEPFILTERS`:** status-filtered measures use it, so a chart split by status shows only the statuses that apply.
- **Card measures:** they end in ` KPI` and wrap the base measure in `COALESCE(..., 0)`, so a card shows 0 instead of blank. Charts keep using the base measures, so empty categories don't appear as zero bars.

## Editing the report as code

`tools/build_pbip.py` writes the model tables (TMDL) and the report pages (PBIR) from Python definitions. It keeps `report.json` and the theme saved by Power BI Desktop. `tools/validate_pbir.py` checks every report file against Microsoft's published JSON schemas.

```bash
python powerbi/tools/build_pbip.py
pip install jsonschema referencing
python powerbi/tools/validate_pbir.py
```

With the project open in Power BI Desktop, report-only changes show an **Apply external changes** banner. Model changes, such as new measures, need the project to be reopened.

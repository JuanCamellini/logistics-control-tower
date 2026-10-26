"""Writes the TMDL tables and the PBIR report pages of the Power BI project.

Run it from the repo root after changing measures or visuals:  python powerbi/tools/build_pbip.py
It keeps report.json and the theme saved by Power BI Desktop and rebuilds only the tables and the pages.
Then validate with:  python powerbi/tools/validate_pbir.py
"""
import json
import shutil
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
TABLES_DIR = ROOT / "OrdenesRetiro.SemanticModel" / "definition" / "tables"
REPORT = ROOT / "OrdenesRetiro.Report"
T = "\t"

# ---------------------------------------------------------------- semantic model
# (column, TMDL dataType, M type)
TEXT, INT, DATE, BOOL = ("string", "type text"), ("int64", "Int64.Type"), ("dateTime", "type date"), ("boolean", "type logical")
TABLES = {
    "dim_carrier": [("carrier_id", TEXT), ("carrier_name", TEXT), ("pickup_sla_days", INT), ("depot_sla_days", INT)],
    "dim_customer": [("customer_id", INT), ("customer_name", TEXT), ("street", TEXT), ("locality", TEXT),
                     ("province", TEXT), ("route_code", TEXT), ("route", TEXT)],
    "dim_date": [("date_key", DATE), ("year", INT), ("month", INT), ("month_name", TEXT), ("is_business_day", BOOL)],
    "meta_snapshot": [("as_of_date", DATE)],
    "fact_pickup_order": [
        ("order_id", INT), ("customer_id", INT), ("carrier_id", TEXT), ("document_date", DATE), ("sent_date", DATE),
        ("expected_pickup_date", DATE), ("pickup_date", DATE), ("expected_arrival_date", DATE), ("arrival_date", DATE),
        ("packages", INT), ("status", TEXT), ("is_critical", BOOL), ("alert_sent", BOOL), ("delay_days", INT),
        ("delay_bucket", TEXT), ("business_days_in_status", INT), ("notes", TEXT), ("incident_category", TEXT),
        ("pickup_business_days", INT), ("pickup_sla_status", TEXT), ("depot_business_days", INT), ("depot_sla_status", TEXT),
    ],
}
# Columns added in Power Query: (table, column, TMDL dataType, M expression, M type)
EXTRA_COLUMNS = {
    "dim_date": [("month_label", "string", 'each Date.ToText([date_key], "yyyy-MM")', "type text")],
    "fact_pickup_order": [(
        "delay_bucket_order", "int64",
        'each if [delay_bucket] = "0 - 7 días" then 1 else if [delay_bucket] = "8 - 15 días" then 2 '
        'else if [delay_bucket] = "16 - 30 días" then 3 else if [delay_bucket] = "31 - 60 días" then 4 '
        'else if [delay_bucket] = null then null else 5',
        "Int64.Type",
    )],
}
SORT_BY = {("fact_pickup_order", "delay_bucket"): "delay_bucket_order"}
KEYS = {("dim_date", "date_key")}

PENDING = '{ "EN GESTION", "RETIRADO" }'
MEASURES = [  # (name, DAX, format)
    ("Órdenes", "COUNTROWS ( fact_pickup_order )", "#,0"),
    ("Bultos", "SUM ( fact_pickup_order[packages] )", "#,0"),
    ("Órdenes Pendientes", f"CALCULATE ( [Órdenes], KEEPFILTERS ( fact_pickup_order[status] IN {PENDING} ) )", "#,0"),
    ("Bultos Pendientes", f"CALCULATE ( [Bultos], KEEPFILTERS ( fact_pickup_order[status] IN {PENDING} ) )", "#,0"),
    ("Órdenes En Gestión", 'CALCULATE ( [Órdenes], KEEPFILTERS ( fact_pickup_order[status] = "EN GESTION" ) )', "#,0"),
    ("Bultos En Gestión", 'CALCULATE ( [Bultos], KEEPFILTERS ( fact_pickup_order[status] = "EN GESTION" ) )', "#,0"),
    ("Órdenes Retiradas", 'CALCULATE ( [Órdenes], KEEPFILTERS ( fact_pickup_order[status] = "RETIRADO" ) )', "#,0"),
    ("Bultos Retirados", 'CALCULATE ( [Bultos], KEEPFILTERS ( fact_pickup_order[status] = "RETIRADO" ) )', "#,0"),
    ("Órdenes Críticas", "CALCULATE ( [Órdenes], KEEPFILTERS ( fact_pickup_order[is_critical] = TRUE () ) )", "#,0"),
    ("Bultos Críticos", "CALCULATE ( [Bultos], KEEPFILTERS ( fact_pickup_order[is_critical] = TRUE () ) )", "#,0"),
    ("% Críticas", "DIVIDE ( COALESCE ( [Órdenes Críticas], 0 ), [Órdenes Pendientes], 0 )", "0.0%;-0.0%;0.0%"),
    ("Órdenes Depuradas", 'CALCULATE ( [Órdenes], KEEPFILTERS ( fact_pickup_order[status] = "DEPURADA" ) )', "#,0"),
    ("% Depuradas", "DIVIDE ( COALESCE ( [Órdenes Depuradas], 0 ), [Órdenes], 0 )", "0.0%;-0.0%;0.0%"),
    ("Tiempo Total del Ciclo (días)",
     'CALCULATE ( AVERAGE ( fact_pickup_order[delay_days] ), KEEPFILTERS ( fact_pickup_order[status] = "EN PUNTO DE CONTROL" ) )', "0.0"),
    ("Promedio Días de Atraso Pendientes",
     f"CALCULATE ( AVERAGE ( fact_pickup_order[delay_days] ), KEEPFILTERS ( fact_pickup_order[status] IN {PENDING} ) )", "0.0"),
    ("Actualizado", '"Actualizado " & FORMAT ( MAX ( meta_snapshot[as_of_date] ), "dd/mm/yyyy" )', None),
    ("Cliente Seleccionado",
     'IF ( HASONEVALUE ( dim_customer[customer_id] ), SELECTEDVALUE ( dim_customer[customer_name] ) & "  ·  N° " & SELECTEDVALUE ( dim_customer[customer_id] ), "Seleccioná un cliente" )',
     None),
    ("Color SLA Retiro",
     'SWITCH ( SELECTEDVALUE ( fact_pickup_order[pickup_sla_status] ), "Fuera de plazo", "#F87171", "En plazo", "#4ADE80", "En curso", "#FBBF24", "#9AA4B2" )',
     None),
    ("Color SLA Rendición",
     'SWITCH ( SELECTEDVALUE ( fact_pickup_order[depot_sla_status] ), "Fuera de plazo", "#F87171", "En plazo", "#4ADE80", "En curso", "#FBBF24", "#9AA4B2" )',
     None),
    ("Cliente Dirección", 'SELECTEDVALUE ( dim_customer[street], "-" )', None),
    ("Cliente Localidad", 'SELECTEDVALUE ( dim_customer[locality], "-" )', None),
    ("Cliente Provincia", 'SELECTEDVALUE ( dim_customer[province], "-" )', None),
    ("Cliente Ruta", 'SELECTEDVALUE ( dim_customer[route], "-" )', None),
    ("Cliente Proveedor",
     'CALCULATE ( SELECTEDVALUE ( dim_carrier[carrier_name], "-" ), CROSSFILTER ( fact_pickup_order[carrier_id], dim_carrier[carrier_id], BOTH ) )',
     None),
    ("Órdenes por Mes",
     "IF ( MIN ( dim_date[date_key] ) <= MAX ( meta_snapshot[as_of_date] ), COALESCE ( [Órdenes], 0 ) )", "#,0"),
    ("Título Depuradas", '"Órdenes depuradas del cliente (" & COALESCE ( [Órdenes Depuradas], 0 ) & ")"', None),
    ("Título Línea de Tiempo", '"Línea de tiempo de sus órdenes (" & COALESCE ( [Órdenes], 0 ) & ")"', None),
    ("Tiempo de Ciclo General", "CALCULATE ( [Tiempo Total del Ciclo (días)], REMOVEFILTERS ( dim_customer ) )", "0.0"),
    ("% Depuradas General", "CALCULATE ( [% Depuradas], REMOVEFILTERS ( dim_customer ) )", "0.0%;-0.0%;0.0%"),
]


KPI_BASES = ["Órdenes", "Bultos", "Órdenes Pendientes", "Bultos Pendientes", "Órdenes En Gestión", "Bultos En Gestión",
             "Órdenes Retiradas", "Bultos Retirados", "Órdenes Críticas", "Bultos Críticos"]
MEASURES += [(f"{m} KPI", f"COALESCE ( [{m}], 0 )", "#,0") for m in KPI_BASES]


def quote(name):
    return name if name.replace("_", "").isalnum() and name.isascii() else "'" + name.replace("'", "''") + "'"


def table_tmdl(table, columns):
    lines = [f"table {table}"]
    if table == "dim_date":
        lines.append(f"{T}dataCategory: Time")
    lines.append("")
    if table == "fact_pickup_order":
        for name, dax, fmt in MEASURES:
            lines.append(f"{T}measure {quote(name)} = {dax}")
            if fmt:
                lines.append(f"{T}{T}formatString: {fmt}")
            lines.append("")
    all_columns = [(c, t[0]) for c, t in columns] + [(c, dt) for c, dt, _, _ in EXTRA_COLUMNS.get(table, [])]
    for col, dtype in all_columns:
        lines.append(f"{T}column {col}")
        lines.append(f"{T}{T}dataType: {dtype}")
        if (table, col) in KEYS:
            lines.append(f"{T}{T}isKey")
        if dtype == "int64":
            lines.append(f"{T}{T}formatString: 0")
        lines.append(f"{T}{T}summarizeBy: none")
        lines.append(f"{T}{T}sourceColumn: {col}")
        if (table, col) in SORT_BY:
            lines.append(f"{T}{T}sortByColumn: {SORT_BY[(table, col)]}")
        if dtype == "dateTime":
            lines.append("")
            lines.append(f"{T}{T}annotation UnderlyingDateTimeDataType = Date")
        lines.append("")

    if table == "fact_pickup_order":
        # Search key for the text search box: order number, customer name and customer number in one field
        lines.append(f"{T}column search_key = FORMAT ( fact_pickup_order[order_id], \"0\" ) & \"  ·  \" & "
                     f"RELATED ( dim_customer[customer_name] ) & \"  ·  \" & FORMAT ( fact_pickup_order[customer_id], \"0\" )")
        lines.append(f"{T}{T}dataType: string")
        lines.append(f"{T}{T}summarizeBy: none")
        lines.append("")

    types = ", ".join(f'{{"{c}", {t[1]}}}' for c, t in columns)
    steps = [
        f'Origen = Csv.Document(File.Contents(CarpetaDatos & "{table}.csv"), [Delimiter = ",", Encoding = 65001, QuoteStyle = QuoteStyle.Csv])',
        "Encabezados = Table.PromoteHeaders(Origen, [PromoteAllScalars = true])",
        'SinVacios = Table.TransformColumns(Encabezados, {}, each if _ = "" then null else _)',
        f'Tipos = Table.TransformColumnTypes(SinVacios, {{{types}}}, "en-US")',
    ]
    last = "Tipos"
    for i, (col, _, expr, mtype) in enumerate(EXTRA_COLUMNS.get(table, [])):
        step = f"Extra{i}"
        steps.append(f'{step} = Table.AddColumn({last}, "{col}", {expr}, {mtype})')
        last = step
    lines.append(f"{T}partition {table} = m")
    lines.append(f"{T}{T}mode: import")
    lines.append(f"{T}{T}source =")
    lines.append(f"{T*4}let")
    for i, step in enumerate(steps):
        lines.append(f"{T*4}    {step}{',' if i < len(steps) - 1 else ''}")
    lines.append(f"{T*4}in")
    lines.append(f"{T*4}    {last}")
    lines.append("")
    return "\n".join(lines) + "\n"


TABLES_DIR.mkdir(parents=True, exist_ok=True)
for table, columns in TABLES.items():
    (TABLES_DIR / f"{table}.tmdl").write_text(table_tmdl(table, columns), encoding="utf-8")

# ---------------------------------------------------------------- report (PBIR)
SCHEMA = "https://developer.microsoft.com/json-schemas/fabric/item/report/definition"
FACT = "fact_pickup_order"

# Palette (dark)
TEXT, MUTED, PANEL, BORDER, HEADER = "#E6E8EB", "#9AA4B2", "#1B1F27", "#2E3440", "#252B36"
BLUE, CYAN, AMBER = "#4F9DFF", "#22D3EE", "#F5B942"
FONT = "'Segoe UI'"


def write_json(path, data):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")


def lit(value):
    return {"expr": {"Literal": {"Value": value}}}


def color(hex_code):
    return {"solid": {"color": lit(f"'{hex_code}'")}}


def props(**kwargs):
    return [{"properties": kwargs}]


def column(entity, prop):
    return {"Column": {"Expression": {"SourceRef": {"Entity": entity}}, "Property": prop}}


def measure(prop):
    return {"Measure": {"Expression": {"SourceRef": {"Entity": FACT}}, "Property": prop}}


def proj(field, display=None):
    kind = "Column" if "Column" in field else "Measure"
    entity = field[kind]["Expression"]["SourceRef"]["Entity"]
    prop = field[kind]["Property"]
    p = {"field": field, "queryRef": f"{entity}.{prop}", "nativeQueryRef": prop}
    if display:
        p["displayName"] = display
    return p


def container(title=None, panel=True, title_measure=None):
    c = {
        "subTitle": props(show=lit("false")),
        "dropShadow": props(show=lit("false")),
        "padding": props(top=lit("6D"), bottom=lit("6D"), left=lit("8D"), right=lit("8D")),
    }
    if panel:
        c["background"] = props(show=lit("true"), color=color(PANEL), transparency=lit("0D"))
        c["border"] = props(show=lit("true"), color=color(BORDER), radius=lit("10D"))
    else:
        c["background"] = props(show=lit("false"))
        c["border"] = props(show=lit("false"))
    if title or title_measure:
        text = {"expr": measure(title_measure)} if title_measure else lit(f"'{title}'")
        c["title"] = props(show=lit("true"), text=text, fontSize=lit("12D"), bold=lit("true"),
                           fontColor=color(TEXT), fontFamily=lit(FONT))
    else:
        c["title"] = props(show=lit("false"))
    return c


def visual(name, vtype, pos, roles=None, title=None, sort=None, objects=None, panel=True, title_measure=None,
           filters=None):
    v = {"visualType": vtype}
    if roles:
        v["query"] = {"queryState": {role: {"projections": items} for role, items in roles.items()}}
        if sort:
            v["query"]["sortDefinition"] = {"sort": [{"field": sort[0], "direction": sort[1]}], "isDefaultSort": False}
    if objects:
        v["objects"] = objects
    v["visualContainerObjects"] = container(title, panel, title_measure)
    v["drillFilterOtherVisuals"] = True
    x, y, w, h = pos
    data = {
        "$schema": f"{SCHEMA}/visualContainer/2.4.0/schema.json",
        "name": name,
        "position": {"x": x, "y": y, "z": 0, "height": h, "width": w, "tabOrder": 0},
        "visual": v,
    }
    if filters:
        data["filterConfig"] = {"filters": filters}
    return name, data


def status_filter(name, value):
    """Visual-level filter: fact_pickup_order[status] = value."""
    return {
        "name": name,
        "field": column(FACT, "status"),
        "type": "Categorical",
        "filter": {
            "Version": 2,
            "From": [{"Name": "f", "Entity": FACT, "Type": 0}],
            "Where": [{"Condition": {"In": {
                "Expressions": [{"Column": {"Expression": {"SourceRef": {"Source": "f"}}, "Property": "status"}}],
                "Values": [[{"Literal": {"Value": f"'{value}'"}}]],
            }}}],
        },
    }


def textbox(name, pos, text, size, align="center", text_color=TEXT):
    objects = {"general": [{"properties": {"paragraphs": [{
        "textRuns": [{"value": text, "textStyle": {"fontWeight": "bold", "fontSize": size, "color": text_color}}],
        "horizontalTextAlignment": align,
    }]}}]}
    return visual(name, "textbox", pos, objects=objects, panel=False)


def subtitle(name, pos, line1, line2):
    objects = {"general": [{"properties": {"paragraphs": [
        {"textRuns": [{"value": line1, "textStyle": {"fontWeight": "bold", "fontSize": "13pt", "color": TEXT}}]},
        {"textRuns": [{"value": line2, "textStyle": {"fontSize": "10pt", "color": MUTED}}]},
    ]}}]}
    return visual(name, "textbox", pos, objects=objects, panel=False)


def card(name, pos, measure_name, label, value_size="22D", show_label=True, title=None):
    objects = {
        "labels": props(fontSize=lit(value_size), color=color(TEXT), labelDisplayUnits=lit("1D"), fontFamily=lit(FONT)),
        "categoryLabels": props(show=lit("true" if show_label else "false"), fontSize=lit("10D"), color=color(MUTED)),
    }
    return visual(name, "card", pos, {"Values": [proj(measure(measure_name), label)]}, title=title, objects=objects)


def multi_card(name, pos, title, measures, value_size="15D"):
    objects = {
        "value": props(fontSize=lit(value_size), fontColor=color(TEXT), labelDisplayUnits=lit("1D")),
        "label": props(show=lit("true"), fontSize=lit("10D"), fontColor=color(MUTED)),
    }
    return visual(name, "cardVisual", pos, {"Data": [proj(measure(m + " KPI" if m in KPI_BASES else m), label) for m, label in measures]},
                  title=title, objects=objects)


def slicer(name, pos, field, label, mode="'Dropdown'"):
    objects = {
        "data": props(mode=lit(mode)),
        # Slicers name their font size "textSize" (fontSize is silently ignored)
        "header": props(show=lit("true"), textSize=lit("10D"), fontColor=color(MUTED)),
        "items": props(textSize=lit("9D" if mode == "'Dropdown'" else "10D"), fontColor=color(TEXT)),
    }
    name, data = visual(name, "slicer", pos, {"Values": [proj(field, label)]}, objects=objects)
    if mode == "'Dropdown'":
        # Narrow dropdowns: thin side padding so long values (TRANSPORTES ANDINOS) fit
        data["visual"]["visualContainerObjects"]["padding"] = props(top=lit("6D"), bottom=lit("6D"), left=lit("2D"),
                                                                    right=lit("2D"))
    return name, data


def search_box(name, pos, field, title, hint):
    return visual(name, "textSlicer", pos, {"Values": [proj(field, hint)]}, title=title)


def chart_objects(legend):
    return {
        "labels": props(show=lit("true"), fontSize=lit("10D"), color=color(TEXT), labelDisplayUnits=lit("1D")),
        "valueAxis": props(show=lit("false"), gridlineShow=lit("false")),
        "categoryAxis": props(show=lit("true"), fontSize=lit("10D"), labelColor=color(TEXT), showAxisTitle=lit("false")),
        "legend": props(show=lit("true" if legend else "false"), position=lit("'Top'"), fontSize=lit("10D"),
                        labelColor=color(MUTED)),
    }


def bar(name, pos, vtype, category, values, title, series=None, sort=None, fill=None):
    roles = {"Category": [proj(category)], "Y": [proj(v) for v in values]}
    if series:
        roles["Series"] = [proj(series)]
    objects = chart_objects(legend=bool(series) or len(values) > 1)
    if fill:
        objects["dataPoint"] = props(fill=color(fill))
    return visual(name, vtype, pos, roles, title=title, sort=sort or (values[0], "Descending"), objects=objects)


def table(name, pos, fields, title=None, sla_colors=False, title_measure=None, filters=None):
    objects = {
        "columnHeaders": props(fontSize=lit("10D"), bold=lit("true"), fontColor=color(TEXT), backColor=color(HEADER)),
        "values": props(fontSize=lit("10D"), fontColorPrimary=color(TEXT), backColorPrimary=color(PANEL),
                        fontColorSecondary=color(TEXT), backColorSecondary=color("#20252E")),
        "grid": props(gridHorizontal=lit("false"), rowPadding=lit("3D")),
        "total": props(totals=lit("false")),
    }
    if sla_colors:
        for col, color_measure in (("pickup_sla_status", "Color SLA Retiro"), ("depot_sla_status", "Color SLA Rendición")):
            objects["values"].append({
                "properties": {"fontColor": {"solid": {"color": {"expr": measure(color_measure)}}}},
                "selector": {"data": [{"dataViewWildcard": {"matchingOption": 1}}], "metadata": f"{FACT}.{col}"},
            })
    return visual(name, "tableEx", pos, {"Values": [proj(f, d) for f, d in fields]}, title=title, objects=objects,
                  title_measure=title_measure, filters=filters)


def back_button(name, pos):
    _, data = visual(name, "actionButton", pos, panel=False)
    data["visual"]["objects"] = {"icon": [{"properties": {"shapeType": lit("'back'")}, "selector": {"id": "default"}}]}
    data["visual"]["visualContainerObjects"]["visualLink"] = props(show=lit("true"), type=lit("'Back'"))
    data["visual"].pop("drillFilterOtherVisuals")
    return name, data


def drill_button(name, pos, page, text):
    _, data = visual(name, "actionButton", pos, panel=False)
    default, disabled = {"id": "default"}, {"id": "disabled"}
    data["visual"]["objects"] = {
        "icon": [{"properties": {"show": lit("false")}, "selector": default}],
        "text": [
            {"properties": {"show": lit("true")}},
            {"properties": {"show": lit("true"), "text": lit(f"'{text}'"), "fontColor": color("#FFFFFF"),
                            "fontSize": lit("10D"), "bold": lit("true"), "verticalAlignment": lit("'middle'"),
                            "horizontalAlignment": lit("'center'")}, "selector": default},
            {"properties": {"show": lit("true"), "text": lit(f"'{text}'"), "fontColor": color(MUTED),
                            "fontSize": lit("10D"), "bold": lit("true")}, "selector": disabled},
        ],
        "fill": [
            {"properties": {"show": lit("true"), "fillColor": color(BLUE), "transparency": lit("0D")}, "selector": default},
            {"properties": {"show": lit("true"), "fillColor": color(BORDER), "transparency": lit("0D")}, "selector": disabled},
        ],
        "outline": [{"properties": {"show": lit("false"), "roundEdge": lit("8D")}, "selector": default}],
    }
    data["visual"]["visualContainerObjects"]["visualLink"] = props(
        show=lit("true"), type=lit("'Drillthrough'"), drillthroughSection=lit(f"'{page}'"),
        disabledTooltip=lit("'Seleccioná una orden de la tabla (o buscá un N° de cliente)'"),
        enabledTooltip=lit("'Abrir el detalle del cliente seleccionado'"),
    )
    data["visual"]["visualContainerObjects"]["padding"] = props(top=lit("0D"), bottom=lit("0D"), left=lit("0D"),
                                                                right=lit("0D"))
    data["visual"].pop("drillFilterOtherVisuals")
    return name, data


PAGE_W = 1280
GAP = 10
ROW_W = PAGE_W - 2 * GAP

# ---------------- main page
main_visuals = [
    subtitle("subtitulo", (10, 10, 280, 58), "Control de Transporte", "Datos ficticios · portfolio"),
    textbox("titulo", (300, 10, 640, 58), "Órdenes de Retiro", "26pt"),
    card("card_actualizado", (950, 10, 320, 58), "Actualizado", None, value_size="13D", show_label=False),
    search_box("buscador", (10, 74, 280, 82), column(FACT, "search_key"), "Buscar orden o cliente", "N° orden o cliente"),
    slicer("slicer_proveedor", (300, 78, 165, 74), column("dim_carrier", "carrier_name"), "Proveedor"),
    slicer("slicer_estado", (475, 78, 165, 74), column(FACT, "status"), "Estado"),
    slicer("slicer_rango", (650, 78, 165, 74), column(FACT, "delay_bucket"), "Rango de atraso"),
    slicer("slicer_ruta", (825, 78, 130, 74), column("dim_customer", "route"), "Ruta"),
    slicer("slicer_fecha", (965, 78, 305, 74), column(FACT, "document_date"), "Fecha del documento", mode="'Between'"),
    multi_card("kpi_total", (10, 162, 220, 110), "Total", [("Órdenes", "Órdenes"), ("Bultos", "Bultos")]),
    multi_card("kpi_gestion", (240, 162, 220, 110), "En gestión",
               [("Órdenes En Gestión", "Órdenes"), ("Bultos En Gestión", "Bultos")]),
    multi_card("kpi_retiradas", (470, 162, 220, 110), "Retiradas",
               [("Órdenes Retiradas", "Órdenes"), ("Bultos Retirados", "Bultos")]),
    multi_card("kpi_criticas", (700, 162, 220, 110), "Críticas",
               [("Órdenes Críticas", "Órdenes"), ("Bultos Críticos", "Bultos")]),
    card("kpi_pct_criticas", (930, 162, 107, 110), "% Críticas", "de pendientes", value_size="18D"),
    card("kpi_pct_depuradas", (1047, 162, 106, 110), "% Depuradas", "depuradas", value_size="18D"),
    card("kpi_ciclo", (1163, 162, 107, 110), "Tiempo Total del Ciclo (días)", "días de ciclo", value_size="18D"),
    textbox("titulo_tabla", (GAP, 280, 400, 42), "Detalle de órdenes", "13pt", align="left"),
    drill_button("boton_detalle_cliente", (1048, 285, 222, 32), "detalle_cliente", "Ver detalle del cliente  ›"),
    table("tabla_detalle", (GAP, 324, ROW_W, 208), [
        (column(FACT, "order_id"), "Orden"), (column(FACT, "document_date"), "Fecha doc"),
        (column("dim_customer", "customer_id"), "N° cliente"), (column("dim_customer", "customer_name"), "Cliente"),
        (column("dim_customer", "locality"), "Localidad"), (column("dim_carrier", "carrier_name"), "Proveedor"),
        (column(FACT, "packages"), "Bultos"), (column(FACT, "status"), "Estado"),
        (column(FACT, "delay_days"), "Días atraso"), (column(FACT, "pickup_date"), "Retiro"),
        (column(FACT, "arrival_date"), "Rendida"), (column(FACT, "notes"), "Observación"),
    ]),
]
chart_w = (ROW_W - 2 * GAP) // 3
cols = [GAP, GAP + chart_w + GAP, GAP + 2 * (chart_w + GAP)]
row1, row2, ch = 542, 822, 270
main_visuals += [
    bar("chart_estado", (cols[0], row1, chart_w, ch), "clusteredBarChart", column(FACT, "status"),
        [measure("Órdenes")], "Órdenes por estado", fill=BLUE),
    bar("chart_proveedor", (cols[1], row1, chart_w, ch), "clusteredBarChart", column("dim_carrier", "carrier_name"),
        [measure("Bultos Pendientes"), measure("Órdenes Pendientes")], "Pendientes por proveedor"),
    bar("chart_antiguedad", (cols[2], row1, chart_w, ch), "barChart", column(FACT, "delay_bucket"),
        [measure("Órdenes Pendientes")], "Antigüedad de las pendientes", series=column(FACT, "status"),
        sort=(column(FACT, "delay_bucket"), "Ascending")),
    bar("chart_motivos", (cols[0], row2, chart_w, ch), "clusteredBarChart", column(FACT, "incident_category"),
        [measure("Órdenes Depuradas")], "Motivos de depuración", fill=AMBER),
    bar("chart_atraso", (cols[1], row2, chart_w, ch), "ribbonChart", column("dim_carrier", "carrier_name"),
        [measure("Promedio Días de Atraso Pendientes")], "Atraso promedio por proveedor (total)",
        series=column(FACT, "status")),
    bar("chart_provincia", (cols[2], row2, chart_w, ch), "clusteredBarChart", column("dim_customer", "province"),
        [measure("Bultos Pendientes")], "Bultos pendientes por provincia", fill=CYAN),
]
MAIN_H = row2 + ch + GAP

# ---------------- drillthrough page
detail_visuals = [
    # Header: back button, page name and the selected customer in large type
    back_button("boton_atras", (10, 18, 44, 44)),
    textbox("titulo_detalle", (60, 10, 330, 60), "Detalle por Cliente", "20pt", align="left", text_color=MUTED),
    card("card_cliente", (400, 10, 870, 60), "Cliente Seleccionado", None, value_size="20D", show_label=False),
    # Customer record: one tile per field
    multi_card("ficha_cliente", (GAP, 80, ROW_W, 100), "Datos del cliente",
               [("Cliente Dirección", "Dirección"), ("Cliente Localidad", "Localidad"),
                ("Cliente Provincia", "Provincia"), ("Cliente Ruta", "Ruta"), ("Cliente Proveedor", "Proveedor")],
               value_size="13D"),
    multi_card("det_pendientes", (10, 190, 300, 110), "Pendientes",
               [("Órdenes Pendientes", "Órdenes"), ("Bultos Pendientes", "Bultos")]),
    card("det_criticas", (320, 190, 200, 110), "Órdenes Críticas KPI", "órdenes críticas"),
    multi_card("det_ciclo", (530, 190, 370, 110), "Tiempo total del ciclo (días)",
               [("Tiempo Total del Ciclo (días)", "Cliente"), ("Tiempo de Ciclo General", "Promedio general")]),
    multi_card("det_depuradas", (910, 190, 360, 110), "% Depuradas",
               [("% Depuradas", "Cliente"), ("% Depuradas General", "Promedio general")]),
    table("tabla_linea_tiempo", (GAP, 310, ROW_W, 330), [
        (column(FACT, "order_id"), "Orden"), (column(FACT, "document_date"), "Creación"),
        (column(FACT, "sent_date"), "Envío"), (column(FACT, "pickup_date"), "Retiro"),
        (column(FACT, "pickup_business_days"), "Días háb. retiro"), (column(FACT, "pickup_sla_status"), "SLA retiro"),
        (column(FACT, "arrival_date"), "Llegada depósito"), (column(FACT, "depot_business_days"), "Días háb. rendición"),
        (column(FACT, "depot_sla_status"), "SLA rendición"), (column(FACT, "status"), "Estado"),
        (column(FACT, "notes"), "Observación"),
    ], title_measure="Título Línea de Tiempo", sla_colors=True),
]
half_w = (ROW_W - GAP) // 2
detail_visuals += [
    # A list reads better than a chart when a customer has only a few purged orders
    table("tabla_depuradas_cliente", (GAP, 650, half_w, 290), [
        (column(FACT, "order_id"), "Orden"), (column(FACT, "document_date"), "Fecha doc"),
        (column(FACT, "incident_category"), "Motivo"), (column(FACT, "notes"), "Observación"),
    ], title_measure="Título Depuradas", filters=[status_filter("solo_depuradas", "DEPURADA")]),
    # Every month of the period is shown, with 0 when the customer had no orders
    bar("chart_mes_cliente", (GAP + half_w + GAP, 650, half_w, 290), "clusteredColumnChart",
        column("dim_date", "month_label"), [measure("Órdenes por Mes")], "Órdenes por mes",
        sort=(column("dim_date", "month_label"), "Ascending"), fill=BLUE),
]
DETAIL_H = 950

DRILL_FIELD = column("dim_customer", "customer_id")
DETAIL_PAGE_EXTRA = {
    "visibility": "HiddenInViewMode",
    "type": "Drillthrough",
    "pageBinding": {
        "name": "3f1c2a7e-9b4d-4c1e-8a5f-2d6e7b9c0a11",
        "type": "Drillthrough",
        "referenceScope": "Default",
        "acceptsFilterContext": "None",
        "parameters": [{"name": "param_cliente", "boundFilter": "filtro_drill_cliente", "fieldExpr": DRILL_FIELD}],
    },
    "filterConfig": {"filters": [{
        "name": "filtro_drill_cliente",
        "field": DRILL_FIELD,
        "type": "Categorical",
        "howCreated": "Drillthrough",
    }]},
}
PAGE_BACKGROUND = {"background": props(color=color("#12151B"), transparency=lit("0D")),
                   "outspace": props(color=color("#0D1015"), transparency=lit("0D"))}

# Keep what Power BI Desktop saved (theme, report settings); rebuild only the pages.
d = REPORT / "definition"
if not (REPORT / "definition.pbir").exists():
    write_json(REPORT / "definition.pbir", {
        "$schema": "https://developer.microsoft.com/json-schemas/fabric/item/report/definitionProperties/2.0.0/schema.json",
        "version": "4.0",
        "datasetReference": {"byPath": {"path": "../OrdenesRetiro.SemanticModel"}},
    })
if not (d / "version.json").exists():
    write_json(d / "version.json", {"$schema": f"{SCHEMA}/versionMetadata/1.0.0/schema.json", "version": "2.0.0"})
if not (d / "report.json").exists():
    write_json(d / "report.json", {
        "$schema": f"{SCHEMA}/report/1.3.0/schema.json",
        "themeCollection": {"baseTheme": {"name": "CY24SU06", "reportVersionAtImport": "5.55", "type": "SharedResources"}},
        "layoutOptimization": "None",
    })
if (d / "pages").exists():
    shutil.rmtree(d / "pages")
write_json(d / "pages" / "pages.json", {
    "$schema": f"{SCHEMA}/pagesMetadata/1.0.0/schema.json",
    "pageOrder": ["principal", "detalle_cliente"],
    "activePageName": "principal",
})
def interactions(names):
    """Who reacts to what on the main page (pairs not listed keep Power BI's default)."""
    rules = {}
    for src in names:
        for dst in names:
            if src == dst:
                continue
            if dst == "chart_atraso":
                rules[src, dst] = "NoFilter"         # carrier benchmark: ignores every filter and selection
            elif src == "tabla_detalle" and dst.startswith("kpi_"):
                rules[src, dst] = "NoFilter"         # selecting a row only picks the customer for the button
            elif src == "tabla_detalle" and dst.startswith("chart_"):
                rules[src, dst] = "HighlightFilter"  # the selected order lights up, the rest goes transparent
            elif src == "buscador" and dst in ("chart_proveedor", "chart_provincia"):
                rules[src, dst] = "NoFilter"         # context charts keep the whole picture while searching
    return [{"source": s, "target": t, "type": k} for (s, t), k in rules.items()]


MAIN_PAGE_EXTRA = {"visualInteractions": interactions([name for name, _ in main_visuals])}
for page, display, visuals, height, extra in (
    ("principal", "Órdenes de Retiro", main_visuals, MAIN_H, MAIN_PAGE_EXTRA),
    ("detalle_cliente", "Detalle por Cliente", detail_visuals, DETAIL_H, DETAIL_PAGE_EXTRA),
):
    write_json(d / "pages" / page / "page.json", {
        "$schema": f"{SCHEMA}/page/2.0.0/schema.json",
        "name": page, "displayName": display, "displayOption": "FitToWidth",
        "height": height, "width": PAGE_W, "objects": PAGE_BACKGROUND, **extra,
    })
    for z, (name, data) in enumerate(visuals):
        data["position"]["z"] = z * 1000
        data["position"]["tabOrder"] = z * 1000
        write_json(d / "pages" / page / "visuals" / name / "visual.json", data)

print("tables:", sorted(p.name for p in TABLES_DIR.iterdir()))
print("visuals:", len(main_visuals), "+", len(detail_visuals), "| heights:", MAIN_H, DETAIL_H)

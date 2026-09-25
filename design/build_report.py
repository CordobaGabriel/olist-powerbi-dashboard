"""Genera las páginas del reporte PBIR (Olist_Dashboard.Report) a partir de layout.json.

Reemplaza todas las páginas y marcadores del reporte por el tablero de Dirección:
fondo generado por build_backgrounds.py, navegación, filtros sincronizados en el
encabezado, tarjetas KPI con variación vs. año anterior y gráficos nativos enlazados
al modelo. Es idempotente: los nombres de visuales y páginas salen de un hash estable.

Uso: python design/build_report.py   (con Power BI Desktop cerrado: guarda el proyecto
solo y pisaría estos archivos)
"""
import hashlib
import json
import shutil

from common import BACKGROUNDS, LAYOUT, PALETTE as C, REPORT, ensure_power_bi_closed, kpi_boxes

DEF = REPORT / "definition"
RES = REPORT / "StaticResources" / "RegisteredResources"

SCHEMA = "https://developer.microsoft.com/json-schemas/fabric/item/report/definition"
VISUAL_SCHEMA = f"{SCHEMA}/visualContainer/2.12.0/schema.json"
PAGE_SCHEMA = f"{SCHEMA}/page/2.1.0/schema.json"
PAGES_SCHEMA = f"{SCHEMA}/pagesMetadata/1.1.0/schema.json"

S = C["series"]
FONT, FONT_SB = "Segoe UI", "Segoe UI Semibold"
THEME_NAME = "OlistDark.json"
YM = "Calendario[Mes Año]"  # eje mensual con etiquetas cortas ("ene 18")
PROJECTION_BLUE = "#8FB6F7"  # proyección: mismo tono que el real, más claro

# Tarjetas con unidades automáticas: 1 decimal (ej. "R$ 8,4 mill.")
ROUNDED = {"Ventas", "Margen Contribución", "Ingresos Productos", "Costo Mercadería", "Meta Ventas Plan",
           "Proyección Cierre Año", "Brecha Proyectada vs Meta", "Cantidad Clientes", "Cantidad Pedidos"}
# Segunda línea opcional de una tarjeta KPI: (medida de texto, medida de color)
KPI_EXTRAS = {"meta": ("Meta Ventas Texto", "@Meta Ventas Color"),
              "proy": ("Cumplimiento Proyectado Texto", "@Cumplimiento Proyectado Color")}


# ---------- expresiones PBIR ----------

def uid(*parts):
    """Nombre estable de 20 caracteres para páginas y visuales."""
    return hashlib.sha1("|".join(parts).encode("utf-8")).hexdigest()[:20]


def lit(value):
    return {"expr": {"Literal": {"Value": value}}}


def text(s):
    return lit("'" + s.replace("'", "''") + "'")


def num(v):
    return lit(f"{v}D")


def color(hex_):
    return {"solid": {"color": lit(f"'{hex_}'")}}


def measure_color(name):
    """Color tomado de una medida que devuelve un hex (formato condicional por valor de campo)."""
    return {"solid": {"color": {"expr": {"Measure": {
        "Expression": {"SourceRef": {"Entity": "Medidas"}}, "Property": name}}}}}


def fg_color(fg):
    """'@Medida' -> color de una medida; '#hex' -> color fijo; None -> texto principal."""
    if fg and fg.startswith("@"):
        return measure_color(fg[1:])
    return color(fg or C["text"])


def field(spec):
    """'[Medida]' -> medida de la tabla Medidas; 'Tabla[Columna]' -> columna."""
    if spec.startswith("["):
        entity, prop, kind = "Medidas", spec[1:-1], "Measure"
    else:
        entity, rest = spec.split("[", 1)
        prop, kind = rest[:-1], "Column"
    return {kind: {"Expression": {"SourceRef": {"Entity": entity}}, "Property": prop}}, entity, prop


def query_ref(spec):
    _, entity, prop = field(spec)
    return f"{entity}.{prop}"


def proj(spec, display=None, active=False):
    expr, entity, prop = field(spec)
    p = {"field": expr, "queryRef": f"{entity}.{prop}", "nativeQueryRef": display or prop}
    if display:
        p["displayName"] = display
    if active:
        p["active"] = True
    return p


def sort_by(spec, direction="Descending"):
    return {"sort": [{"field": field(spec)[0], "direction": direction}], "isDefaultSort": True}


def per_series(prop_name, values):
    """Una propiedad distinta por serie (medida), usando el selector de metadatos."""
    return [{"properties": {prop_name: v}, "selector": {"metadata": query_ref(spec)}} for spec, v in values]


def default_filter(spec, literal):
    """Selección inicial de un filtro (literal DAX: '2018L', '1.2D')."""
    entity, prop = field(spec)[1:]
    return {
        "Version": 2,
        "From": [{"Name": "c", "Entity": entity, "Type": 0}],
        "Where": [{"Condition": {"In": {
            "Expressions": [{"Column": {"Expression": {"SourceRef": {"Source": "c"}}, "Property": prop}}],
            "Values": [[{"Literal": {"Value": literal}}]]}}}],
    }


def box(x, y, w, h):
    return {"x": x, "y": y, "w": w, "h": h}


def inset(r, d):
    return box(r["x"] + d, r["y"] + d, r["w"] - 2 * d, r["h"] - 2 * d)


def container(name, pos, z, visual, title=None, subtitle=None):
    """Contenedor del visual: sin fondo, borde ni encabezado; título/subtítulo opcionales."""
    vco = {
        "background": [{"properties": {"show": lit("false")}}],
        "border": [{"properties": {"show": lit("false")}}],
        "dropShadow": [{"properties": {"show": lit("false")}}],
        "visualHeader": [{"properties": {"show": lit("false")}}],
        "title": [{"properties": {"show": lit("false")}}],
    }
    if title:
        vco["title"] = [{"properties": {
            "show": lit("true"), "text": text(title), "fontColor": color(C["text"]),
            "fontSize": num(12), "fontFamily": text(FONT_SB), "bold": lit("false"),
            "alignment": text("left")}}]
        vco["padding"] = [{"properties": {"top": num(6), "left": num(6), "right": num(6), "bottom": num(4)}}]
    if subtitle:
        vco["subTitle"] = [{"properties": {
            "show": lit("true"), "text": text(subtitle), "fontColor": color(C["muted"]),
            "fontSize": num(9), "fontFamily": text(FONT), "alignment": text("left")}}]
    for k, v in vco.items():
        visual.setdefault("visualContainerObjects", {}).setdefault(k, v)
    visual["drillFilterOtherVisuals"] = True
    return {
        "$schema": VISUAL_SCHEMA,
        "name": name,
        "position": {"x": round(pos["x"], 2), "y": round(pos["y"], 2), "z": z,
                     "height": round(pos["h"], 2), "width": round(pos["w"], 2), "tabOrder": z},
        "visual": visual,
    }


# ---------- visuales comunes a todas las páginas ----------

def card(name, pos, z, measure, size=22, font=FONT_SB, fg=None, label=None, precision=None):
    """Tarjeta con el valor de una medida. La etiqueta la dibuja el fondo, salvo que se pida 'label'."""
    labels = {"fontSize": num(size), "fontFamily": text(font), "color": fg_color(fg)}
    if precision is not None:
        labels["labelPrecision"] = lit(f"{precision}L")
    visual = {
        "visualType": "card",
        "query": {"queryState": {"Values": {"projections": [proj(f"[{measure}]", display=label)]}}},
        "objects": {
            "labels": [{"properties": labels}],
            "categoryLabels": [{"properties": {"show": lit("true" if label else "false"),
                                               "color": color(C["muted"]), "fontSize": num(9)}}],
        },
    }
    return container(name, pos, z, visual)


def nav_button(page, target, i, pages_by_id):
    nav = LAYOUT["rail"]["nav"]
    pos = box(nav["x"], nav["y"] + i * (nav["h"] + nav["gap"]), nav["w"], nav["h"])
    active = target["id"] == page["id"]
    visual = {
        "visualType": "actionButton",
        "objects": {
            "icon": [{"properties": {"shapeType": text("blank")}, "selector": {"id": "default"}}],
            "outline": [{"properties": {"show": lit("false"), "weight": num(0)}},
                        {"properties": {"show": lit("false"), "weight": num(0)}, "selector": {"id": "default"}}],
            "fill": [
                {"properties": {"show": lit("true")}},
                {"properties": {"fillColor": color(S[0]), "transparency": lit("100D")}, "selector": {"id": "default"}},
                {"properties": {"fillColor": color(S[0]), "transparency": lit("88D")}, "selector": {"id": "hover"}},
            ],
            "text": [
                {"properties": {"show": lit("true")}},
                {"properties": {"text": text(target["name"]),
                                "fontColor": color(C["text"] if active else C["muted"]),
                                "fontSize": num(11), "fontFamily": text(FONT_SB if active else FONT),
                                "horizontalAlignment": text("left"), "leftMargin": num(16)},
                 "selector": {"id": "default"}},
                {"properties": {"fontColor": color(C["text"])}, "selector": {"id": "hover"}},
            ],
        },
        "visualContainerObjects": {
            "visualLink": [{"properties": {"show": lit("true"), "type": text("PageNavigation"),
                                           "navigationSection": text(pages_by_id[target["id"]])}}],
        },
    }
    return container(uid(page["id"], "nav", target["id"]), pos, 1000 + i, visual)


def header_slicer(page, f, i):
    """Filtro desplegable del encabezado, sincronizado entre páginas."""
    objects = {
        "data": [{"properties": {"mode": text("Dropdown")}}],
        "header": [{"properties": {"show": lit("true"), "fontColor": color(C["muted"]), "textSize": num(9),
                                   "fontFamily": text(FONT)}}],
        "items": [{"properties": {"fontColor": color(C["text"]), "background": color(C["panel"]),
                                  "textSize": num(10), "fontFamily": text(FONT)}}],
    }
    if "default" in f:
        objects["selection"] = [{"properties": {"singleSelect": lit("true")}}]
        objects["general"] = [{"properties": {"filter": {"filter": default_filter(f["field"], f"{f['default']}L")}}}]
    visual = {
        "visualType": "slicer",
        "query": {"queryState": {"Values": {"projections": [proj(f["field"], active=True)]}}},
        "objects": objects,
        "syncGroup": {"groupName": f["id"], "fieldChanges": True, "filterChanges": True},
    }
    return container(uid(page["id"], "filtro", f["id"]), box(f["x"], f["y"], f["w"], f["h"]), 2000 + i, visual)


def param_slicer(name, pos, z, spec, label, default):
    """Filtro de un parámetro de escenario (selección única, con valor inicial)."""
    visual = {
        "visualType": "slicer",
        "query": {"queryState": {"Values": {"projections": [proj(spec, label, active=True)]}}},
        "objects": {
            "data": [{"properties": {"mode": text("Dropdown")}}],
            "selection": [{"properties": {"singleSelect": lit("true")}}],
            "header": [{"properties": {"show": lit("true"), "fontColor": color(C["muted"]), "textSize": num(9)}}],
            "items": [{"properties": {"fontColor": color(C["text"]), "background": color(C["panel_hi"]),
                                      "textSize": num(10)}}],
            "general": [{"properties": {"filter": {"filter": default_filter(spec, f"{default}D")}}}],
        },
    }
    return container(name, pos, z, visual)


def kpi_tiles(page):
    """Tarjeta KPI: etiqueta (en el fondo) + valor + variación vs. año anterior + línea extra opcional.
    El bloque se centra verticalmente según cuántas líneas lleva debajo del valor."""
    out = []
    for i, (tile, k) in enumerate(zip(kpi_boxes(page), page["kpis"])):
        x, y, w = tile["x"], tile["y"], tile["w"]
        base = uid(page["id"], "kpi", str(i))
        lines = []
        if "delta" in k:
            lines.append((f"Δ {k['delta']} Texto", f"@Δ {k['delta']} Color"))
        if k.get("extra"):
            lines.append(KPI_EXTRAS[k["extra"]])
        top = {0: 36, 1: 30, 2: 24}[len(lines)]
        out.append(card(base + "v", box(x + 8, y + top, w - 16, 46), 3000 + i * 3, k["measure"], size=22,
                        precision=1 if k["measure"] in ROUNDED else None))
        for j, (measure, fg) in enumerate(lines):
            suffix = ("d", "x")[j]  # d = variación, x = línea extra
            out.append(card(base + suffix, box(x + 8, y + top + 46 + j * 24, w - 16, 24), 3001 + i * 3 + j,
                            measure, size=10, font=FONT, fg=fg))
    return out


def footer_card(page):
    f = LAYOUT["rail"]["footer"]
    return card(uid(page["id"], "footer"), box(12, f["y"], 176, f["h"]), 1900, "Texto Fecha Datos",
                size=9.5, font=FONT, fg=C["text2"])


# ---------- formato de gráficos y tablas ----------

AXES = {
    "categoryAxis": [{"properties": {"showAxisTitle": lit("false"), "labelColor": color(C["muted"]),
                                     "fontSize": num(9), "gridlineShow": lit("false")}}],
    "valueAxis": [{"properties": {"showAxisTitle": lit("false"), "labelColor": color(C["muted"]),
                                  "fontSize": num(9), "gridlineShow": lit("true"),
                                  "gridlineColor": color(C["border"]), "gridlineStyle": text("solid")}}],
    "legend": [{"properties": {"show": lit("true"), "position": text("Top"),
                               "labelColor": color(C["text2"]), "fontSize": num(9)}}],
}
NO_LEGEND = {"legend": [{"properties": {"show": lit("false")}}]}
BAR_LABELS = {"labels": [{"properties": {"show": lit("true"), "color": color(C["text2"]), "fontSize": num(9)}}]}
FULL_LABELS = {"labels": [{"properties": {"show": lit("true"), "color": color(C["text2"]), "fontSize": num(9),
                                          "labelDisplayUnits": num(1)}}]}  # números completos, sin "mil"
SINGLE_BLUE = {"dataPoint": [{"properties": {"fill": color(S[0])}}]}


def line_styles(series):
    """series: [(spec, color, estilo)] -> color y estilo de línea por serie.
    Se escriben los dos nombres de propiedad de estilo porque varían según la versión de Power BI."""
    dashed = [(s, text(st)) for s, _, st in series if st != "solid"]
    return {
        "dataPoint": per_series("fill", [(s, color(c)) for s, c, _ in series]),
        "lineStyles": [{"properties": {"strokeWidth": num(2), "showMarker": lit("false")}}]
        + per_series("lineStyle", dashed) + per_series("strokeLineStyle", dashed),
    }


def table_objects(widths, image_height=20):
    """Tabla sobria: separadores horizontales finos, sin ajuste de línea, anchos por columna."""
    return {
        "grid": [{"properties": {
            "gridHorizontal": lit("true"), "gridHorizontalColor": color(C["border"]), "gridHorizontalWeight": num(1),
            "gridVertical": lit("false"), "rowPadding": num(4), "imageHeight": num(image_height),
            "imageWidth": num(150), "outlineColor": color(C["border"])}}],
        "columnHeaders": [{"properties": {"fontColor": color(C["muted"]), "backColor": color(C["panel"]),
                                          "fontSize": num(9), "fontFamily": text(FONT_SB), "outline": text("None"),
                                          "wordWrap": lit("false")}}],
        "values": [{"properties": {"fontColorPrimary": color(C["text"]), "backColorPrimary": color(C["panel"]),
                                   "fontColorSecondary": color(C["text"]), "backColorSecondary": color(C["panel"]),
                                   "fontSize": num(10), "fontFamily": text(FONT), "wordWrap": lit("false")}}],
        "total": [{"properties": {"totals": lit("false")}}],
        "columnWidth": [{"properties": {"value": num(w)}, "selector": {"metadata": query_ref(s)}}
                        for s, w in widths],
    }


def matrix_objects():
    """Matriz de cohortes: celdas SVG, sin subtotales."""
    objects = table_objects([])
    objects["grid"][0]["properties"].update({"imageHeight": num(22), "imageWidth": num(52)})
    objects["rowHeaders"] = [{"properties": {"fontColor": color(C["text2"]), "backColor": color(C["panel"]),
                                             "fontSize": num(10), "fontFamily": text(FONT), "outline": text("None")}}]
    objects["subTotals"] = [{"properties": {"rowSubtotals": lit("false"), "columnSubtotals": lit("false")}}]
    return objects


class Page:
    """Arma los visuales de una página: gráficos dentro de los paneles y tarjetas de conclusión."""

    def __init__(self, spec):
        self.spec = spec
        self.id = spec["id"]
        self.grid = LAYOUT["grids"][spec["grid"]]
        self.charts = []
        self.extras = []

    def chart(self, slot, vtype, roles, sort=None, objects=None):
        """Gráfico que ocupa un panel, con el título y subtítulo definidos en layout.json."""
        query = {"queryState": {r: {"projections": p} for r, p in roles.items()}}
        if sort:
            query["sortDefinition"] = sort
        panel = self.spec["panels"][slot]
        visual = {"visualType": vtype, "query": query, "objects": objects or {}}
        self.charts.append(container(uid(self.id, "chart", slot), inset(self.grid[slot], 8),
                                     4000 + len(self.charts), visual,
                                     title=panel.get("title"), subtitle=panel.get("subtitle")))

    def add(self, visual):
        self.extras.append(visual)

    def visuals(self):
        return self.charts + self.extras


def resumen(p):
    p.chart("left", "lineChart", {
        "Category": [proj(YM, active=True)],
        "Y": [proj("[Ventas]", "Real"), proj("[Meta Ventas Plan]", "Meta"), proj("[Ventas AA]", "Año anterior")],
    }, sort_by(YM, "Ascending"), {**AXES, **line_styles([
        ("[Ventas]", S[0], "solid"), ("[Meta Ventas Plan]", S[3], "dashed"), ("[Ventas AA]", C["context"], "solid")])})
    p.chart("rtop", "tableEx", {
        "Values": [proj("Productos[Macro Categoría]", "Macro categoría"), proj("[Ventas]"),
                   proj("[SVG Cumplimiento Meta]", "Cumplimiento de meta")],
    }, sort_by("[SVG Cumplimiento Meta]", "Ascending"),  # el SVG ordena por cumplimiento (ver medida)
        table_objects([("Productos[Macro Categoría]", 124), ("[Ventas]", 90), ("[SVG Cumplimiento Meta]", 150)]))
    r = p.grid["rbot"]
    p.add(card(uid(p.id, "proy", "v"), box(r["x"] + 12, r["y"] + 38, r["w"] - 24, 50), 5000,
               "Proyección Cierre Año", size=26, precision=1))
    p.add(card(uid(p.id, "proy", "c"), box(r["x"] + 12, r["y"] + 90, r["w"] - 24, 22), 5001,
               "Cumplimiento Proyectado Texto", size=11, font=FONT_SB, fg="@Cumplimiento Proyectado Color"))
    p.add(card(uid(p.id, "proy", "m"), box(r["x"] + 12, r["y"] + 114, r["w"] - 24, 22), 5002,
               "Texto Meta Anual", size=10, font=FONT, fg=C["muted"]))


def rentabilidad(p):
    p.chart("left", "barChart", {
        "Category": [proj("Productos[Macro Categoría]", active=True)],
        "Y": [proj("[Margen Contribución]", "Margen")],
        "Tooltips": [proj("[% Margen Contribución]", "% margen")],
    }, sort_by("[Margen Contribución]"), {**AXES, **NO_LEGEND, **BAR_LABELS, **SINGLE_BLUE})
    p.chart("rtop", "tableEx", {
        "Values": [proj("Productos[Categoría]", "Categoría"), proj("[Margen Contribución]", "Margen"),
                   proj("[% Margen Contribución]", "% margen"), proj("[SVG Barra Margen]", "Pareto")],
    }, sort_by("[Margen Contribución]"), table_objects([
        ("Productos[Categoría]", 144), ("[Margen Contribución]", 84), ("[% Margen Contribución]", 72),
        ("[SVG Barra Margen]", 150)]))
    r = p.grid["rbot"]
    p.add(card(uid(p.id, "pareto"), box(r["x"] + 12, r["y"] + 40, r["w"] - 24, 50), 5000, "Texto Pareto", size=24))


def operacion(p):
    p.chart("left", "columnChart", {
        "Category": [proj(YM, active=True)],
        "Y": [proj("[Retrasos por Tránsito]", "Demora del transportista"),
              proj("[Retrasos por Despacho]", "Despacho tardío del vendedor")],
    }, sort_by(YM, "Ascending"), {**AXES, "dataPoint": per_series("fill", [
        ("[Retrasos por Tránsito]", color(S[0])), ("[Retrasos por Despacho]", color(S[1]))])})
    p.chart("right", "tableEx", {
        "Values": [proj("Vendedores[Vendedor]", "Vendedor"), proj("[Pedidos Vendedor]", "Pedidos"),
                   proj("[% Retraso Vendedor]", "% tarde"), proj("[Días Despacho Vendedor (≥50)]", "Días"),
                   proj("[SVG Puntaje Vendedor]", "Puntaje")],
    }, sort_by("[% Retraso Vendedor]"), table_objects([
        ("Vendedores[Vendedor]", 80), ("[Pedidos Vendedor]", 52), ("[% Retraso Vendedor]", 56),
        ("[Días Despacho Vendedor (≥50)]", 42), ("[SVG Puntaje Vendedor]", 110)], image_height=16))


def clientes(p):
    p.chart("left", "pivotTable", {
        "Rows": [proj("Clientes[Cohorte]", "Cohorte", active=True)],
        "Columns": [proj("Meses de Vida[Mes de Vida]", "Mes", active=True)],
        "Values": [proj("[SVG Retención]", "Retención")],
    }, objects=matrix_objects())
    p.chart("rtop", "barChart", {
        "Category": [proj("Clientes[Frecuencia Compra]", active=True)],
        "Y": [proj("[Cantidad Clientes]", "Clientes")],
    }, sort_by("Clientes[Frecuencia Compra]", "Ascending"), {**AXES, **NO_LEGEND, **FULL_LABELS, **SINGLE_BLUE})
    p.chart("rbot", "barChart", {
        "Category": [proj("Pedidos[Rango Ticket]", active=True)],
        "Y": [proj("[Ventas]")],
    }, sort_by("Pedidos[Rango Ticket]", "Ascending"), {**AXES, **NO_LEGEND, **BAR_LABELS, **SINGLE_BLUE})


def planificacion(p):
    p.chart("left", "lineChart", {
        "Category": [proj(YM, active=True)],
        "Y": [proj("[Ventas]", "Real"), proj("[Ventas Proyectadas]", "Proyección"),
              proj("[Meta Ventas Plan]", "Meta")],
    }, sort_by(YM, "Ascending"), {**AXES, **line_styles([
        ("[Ventas]", S[0], "solid"), ("[Ventas Proyectadas]", PROJECTION_BLUE, "dashed"),
        ("[Meta Ventas Plan]", S[3], "dotted")])})
    r = p.grid["rtop"]
    p.add(param_slicer(uid(p.id, "p", "crec"), box(r["x"] + 16, r["y"] + 62, 150, 50), 5000,
                       "Crecimiento Objetivo[Crecimiento Objetivo]", "Crecimiento objetivo", 1.2))
    p.add(card(uid(p.id, "p", "meta"), box(r["x"] + 184, r["y"] + 56, r["w"] - 200, 64), 5001,
               "Meta Ventas Plan", size=20, label="Meta del año", precision=1))
    p.add(card(uid(p.id, "p", "cump"), box(r["x"] + 16, r["y"] + 136, r["w"] - 32, 24), 5002,
               "Cumplimiento Proyectado Texto", size=11, font=FONT_SB, fg="@Cumplimiento Proyectado Color"))
    r = p.grid["rbot"]
    p.add(param_slicer(uid(p.id, "p", "red"), box(r["x"] + 16, r["y"] + 62, 150, 50), 5010,
                       "Reducción Retrasos[Reducción Retrasos]", "Retrasos evitados", 0.5))
    w = (r["w"] - 32 - 16) / 3
    for i, (m, label) in enumerate([("Puntaje Escenario", "Puntaje estimado"),
                                    ("Mejora Puntaje Escenario", "Mejora vs. hoy"),
                                    ("% Retraso Escenario", "Entregas tarde")]):
        p.add(card(uid(p.id, "esc", m), box(r["x"] + 16 + i * (w + 8), r["y"] + 140, w, 80), 5011 + i,
                   m, size=20, label=label))


PAGE_BUILDERS = {"resumen": resumen, "rentabilidad": rentabilidad, "operacion": operacion,
                 "clientes": clientes, "planificacion": planificacion}


# ---------- página, tema y recursos ----------

def page_json(page, pid):
    bg = f"bg_{page['id']}.png"
    return {
        "$schema": PAGE_SCHEMA,
        "name": pid,
        "displayName": page["name"],
        "displayOption": "FitToPage",
        "height": LAYOUT["canvas"]["height"],
        "width": LAYOUT["canvas"]["width"],
        "objects": {
            "background": [{"properties": {
                "image": {"image": {
                    "name": text(bg),
                    "url": {"expr": {"ResourcePackageItem": {
                        "PackageName": "RegisteredResources", "PackageType": 1, "ItemName": bg}}},
                    "scaling": text("Fit"),
                }},
                "transparency": lit("0D"),
            }}],
            "outspace": [{"properties": {"color": color(C["bg"]), "transparency": lit("0D")}}],
        },
    }


def theme():
    """Tema del reporte: valores por defecto para lo que los visuales no definen explícitamente."""
    def solid(h):
        return {"solid": {"color": h}}

    return {
        "name": "Olist Dark",
        "dataColors": S + ["#6DA7EC", "#E66767", "#48B98F", "#E0B04A", "#B3AAF0"],
        "background": C["panel"], "foreground": C["text"], "tableAccent": S[0],
        "good": C["good"], "neutral": C["warning"], "bad": C["critical"],
        "maximum": S[0], "center": C["context"], "minimum": C["panel_hi"],
        "textClasses": {
            "callout": {"fontSize": 22, "fontFace": FONT_SB, "color": C["text"]},
            "title": {"fontSize": 12, "fontFace": FONT_SB, "color": C["text"]},
            "header": {"fontSize": 11, "fontFace": FONT_SB, "color": C["text"]},
            "label": {"fontSize": 9, "fontFace": FONT, "color": C["muted"]},
        },
        "visualStyles": {
            "*": {"*": {
                "background": [{"show": False}],
                "border": [{"show": False}],
                "dropShadow": [{"show": False}],
                "visualHeader": [{"show": False}],
                "title": [{"fontColor": solid(C["text"]), "fontSize": 12, "fontFamily": FONT_SB}],
                "subTitle": [{"fontColor": solid(C["muted"]), "fontSize": 9}],
                "visualTooltip": [{"background": solid(C["rail"]), "titleFontColor": solid(C["muted"]),
                                   "valueFontColor": solid(C["text"])}],
                "categoryAxis": [{"labelColor": solid(C["muted"]), "gridlineShow": False, "showAxisTitle": False}],
                "valueAxis": [{"labelColor": solid(C["muted"]), "gridlineColor": solid(C["border"]),
                               "showAxisTitle": False}],
                "legend": [{"labelColor": solid(C["text2"]), "position": "Top"}],
                "labels": [{"color": solid(C["text2"])}],
                "outspacePane": [{"backgroundColor": solid(C["rail"]), "foregroundColor": solid(C["text"]),
                                  "borderColor": solid(C["border"])}],
                "filterCard": [{"$id": "Available", "backgroundColor": solid(C["panel"]),
                                "foregroundColor": solid(C["text"]), "borderColor": solid(C["border"])},
                               {"$id": "Applied", "backgroundColor": solid(C["panel_hi"]),
                                "foregroundColor": solid(C["text"]), "borderColor": solid(C["border"])}],
            }},
            "page": {"*": {"outspace": [{"color": solid(C["bg"])}]}},
            "slicer": {"*": {
                "items": [{"fontColor": solid(C["text"]), "background": solid(C["panel"])}],
                "header": [{"fontColor": solid(C["muted"])}],
            }},
            "tableEx": {"*": {
                "grid": [{"gridHorizontalColor": solid(C["border"]), "outlineColor": solid(C["border"])}],
                "columnHeaders": [{"fontColor": solid(C["muted"]), "backColor": solid(C["panel"])}],
                "values": [{"fontColorPrimary": solid(C["text"]), "backColorPrimary": solid(C["panel"]),
                            "fontColorSecondary": solid(C["text"]), "backColorSecondary": solid(C["panel"])}],
            }},
            "pivotTable": {"*": {
                "columnHeaders": [{"fontColor": solid(C["muted"]), "backColor": solid(C["panel"])}],
                "rowHeaders": [{"fontColor": solid(C["text2"]), "backColor": solid(C["panel"])}],
                "values": [{"fontColorPrimary": solid(C["text"]), "backColorPrimary": solid(C["panel"]),
                            "fontColorSecondary": solid(C["text"]), "backColorSecondary": solid(C["panel"])}],
            }},
        },
    }


def write(path, data):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")


def write_resources():
    """Deja en RegisteredResources solo el tema y los fondos actuales, y los registra en report.json."""
    for old in RES.glob("*"):
        old.unlink()
    write(RES / THEME_NAME, theme())
    for p in LAYOUT["pages"]:
        shutil.copyfile(BACKGROUNDS / f"{p['id']}.png", RES / f"bg_{p['id']}.png")
    path = DEF / "report.json"
    report = json.loads(path.read_text(encoding="utf-8"))
    report["themeCollection"]["customTheme"]["name"] = THEME_NAME
    items = [{"name": THEME_NAME, "path": THEME_NAME, "type": "CustomTheme"}]
    items += [{"name": f"bg_{p['id']}.png", "path": f"bg_{p['id']}.png", "type": "Image"} for p in LAYOUT["pages"]]
    report["resourcePackages"] = [pkg for pkg in report["resourcePackages"] if pkg["name"] != "RegisteredResources"]
    report["resourcePackages"].append({"name": "RegisteredResources", "type": "RegisteredResources", "items": items})
    report.setdefault("objects", {})["outspacePane"] = [{"properties": {
        "expanded": lit("false"), "visible": lit("true")}}]
    write(path, report)


def main():
    ensure_power_bi_closed()
    write_resources()
    shutil.rmtree(DEF / "pages", ignore_errors=True)
    shutil.rmtree(DEF / "bookmarks", ignore_errors=True)

    pages_by_id = {p["id"]: uid("page", p["id"]) for p in LAYOUT["pages"]}
    for page in LAYOUT["pages"]:
        pid = pages_by_id[page["id"]]
        pdir = DEF / "pages" / pid
        write(pdir / "page.json", page_json(page, pid))
        builder = Page(page)
        PAGE_BUILDERS[page["id"]](builder)
        visuals = [nav_button(page, t, i, pages_by_id) for i, t in enumerate(LAYOUT["pages"])]
        visuals.append(footer_card(page))
        visuals += [header_slicer(page, f, i) for i, f in enumerate(LAYOUT["header"]["filters"])]
        visuals += kpi_tiles(page)
        visuals += builder.visuals()
        for v in visuals:
            write(pdir / "visuals" / v["name"] / "visual.json", v)
        print(f"{page['name']}: {len(visuals)} visuales")

    write(DEF / "pages" / "pages.json", {
        "$schema": PAGES_SCHEMA,
        "pageOrder": [pages_by_id[p["id"]] for p in LAYOUT["pages"]],
        "activePageName": pages_by_id[LAYOUT["pages"][0]["id"]],
    })


if __name__ == "__main__":
    main()

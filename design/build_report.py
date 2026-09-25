"""Genera las páginas del reporte PBIR (Olist_Dashboard.Report) a partir de layout.json.

Reemplaza todas las páginas y marcadores del reporte por las páginas del rediseño:
fondo generado por build_backgrounds.py, navegación, slicers sincronizados, tarjetas
KPI y gráficos nativos enlazados al modelo en estrella. Es idempotente: se puede
volver a correr después de cambiar layout.json o este script.

Power BI Desktop tiene que estar cerrado mientras corre.
"""
import hashlib
import json
import shutil
from pathlib import Path

DESIGN = Path(__file__).parent
REPORT = DESIGN.parent / "Olist_Dashboard.Report"
DEF = REPORT / "definition"
RES = REPORT / "StaticResources" / "RegisteredResources"

SCHEMA = "https://developer.microsoft.com/json-schemas/fabric/item/report/definition"
VISUAL_SCHEMA = f"{SCHEMA}/visualContainer/2.12.0/schema.json"
PAGE_SCHEMA = f"{SCHEMA}/page/2.1.0/schema.json"
PAGES_SCHEMA = f"{SCHEMA}/pagesMetadata/1.1.0/schema.json"

layout = json.loads((DESIGN / "layout.json").read_text(encoding="utf-8"))
C = layout["palette"]
THEME_NAME = "OlistDark.json"
LOGO = "olist_logo5220036228758551.png"

# Etiquetas cortas para las tarjetas KPI (el nombre de la medida es más largo)
KPI_LABELS = {
    "Cantidad Pedidos": "Pedidos",
    "Cantidad Clientes": "Clientes",
    "Cantidad Ítems": "Ítems vendidos",
    "Cantidad Reseñas": "Reseñas",
    "% Entregas con Retraso": "Entregas con retraso",
    "Días Entrega Promedio": "Días de entrega",
    "Días Entrega Estimados Promedio": "Días estimados",
    "Costo Envío Promedio": "Envío medio por ítem",
    "% Clientes Recurrentes": "Clientes recurrentes",
    "% Reseñas Positivas (4-5)": "Reseñas 4-5 ★",
    "Puntaje Promedio": "Puntaje promedio",
}


# ---------- helpers de expresiones PBIR ----------

def uid(*parts):
    return hashlib.sha1("|".join(parts).encode("utf-8")).hexdigest()[:20]


def lit(value):
    return {"expr": {"Literal": {"Value": value}}}


def text(s):
    return lit("'" + s.replace("'", "''") + "'")


def color(hex_):
    return {"solid": {"color": lit(f"'{hex_}'")}}


def field(spec):
    """'[Medida]' -> medida de la tabla Medidas; 'Tabla[Columna]' -> columna."""
    if spec.startswith("["):
        entity, prop, kind = "Medidas", spec[1:-1], "Measure"
    else:
        entity, rest = spec.split("[", 1)
        prop, kind = rest[:-1], "Column"
    expr = {kind: {"Expression": {"SourceRef": {"Entity": entity}}, "Property": prop}}
    return expr, entity, prop


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


def series_colors(column_spec, colors):
    """dataPoint con un color fijo por valor de una columna de serie."""
    col = field(column_spec)[0]
    return [{
        "properties": {"fill": color(hex_)},
        "selector": {"data": [{"scopeId": {"Comparison": {
            "ComparisonKind": 0, "Left": col, "Right": {"Literal": {"Value": "'" + value + "'"}}}}}]},
    } for value, hex_ in colors.items()]


def container(name, pos, z, visual, title=None):
    vco = {
        "background": [{"properties": {"show": lit("false")}}],
        "border": [{"properties": {"show": lit("false")}}],
        "dropShadow": [{"properties": {"show": lit("false")}}],
        "title": [{"properties": {"show": lit("true" if title else "false"),
                                  **({"text": text(title)} if title else {})}}],
    }
    visual.setdefault("visualContainerObjects", {}).update(
        {k: v for k, v in vco.items() if k not in visual["visualContainerObjects"]})
    visual["drillFilterOtherVisuals"] = True
    return {
        "$schema": VISUAL_SCHEMA,
        "name": name,
        "position": {"x": round(pos["x"], 2), "y": round(pos["y"], 2), "z": z,
                     "height": round(pos["h"], 2), "width": round(pos["w"], 2), "tabOrder": z},
        "visual": visual,
    }


def inset(r, dx, dy=None):
    dy = dx if dy is None else dy
    return {"x": r["x"] + dx, "y": r["y"] + dy, "w": r["w"] - 2 * dx, "h": r["h"] - 2 * dy}


# ---------- visuales ----------

def nav_button(page, target, i, pages_by_id):
    nav = layout["rail"]["nav"]
    h, gap = 38, 8
    pos = {"x": nav["x"], "y": nav["y"] + i * (h + gap), "w": nav["w"], "h": h}
    active = target["id"] == page["id"]
    visual = {
        "visualType": "actionButton",
        "objects": {
            "icon": [{"properties": {"shapeType": text("blank")}, "selector": {"id": "default"}}],
            "outline": [{"properties": {"show": lit("false")}, "selector": {"id": "default"}}],
            "fill": [
                {"properties": {"show": lit("true")}},
                {"properties": {"fillColor": color(C["blue"]),
                                "transparency": lit("70D" if active else "100D")},
                 "selector": {"id": "default"}},
                {"properties": {"fillColor": color(C["blue"]), "transparency": lit("85D")},
                 "selector": {"id": "hover"}},
            ],
            "text": [
                {"properties": {"show": lit("true")}},
                {"properties": {"text": text(target["name"]),
                                "fontColor": color(C["text"] if active else C["muted"]),
                                "fontSize": lit("11D"),
                                "bold": lit("true" if active else "false"),
                                "horizontalAlignment": text("left"),
                                "leftMargin": lit("14D")},
                 "selector": {"id": "default"}},
            ],
        },
        "visualContainerObjects": {
            "visualLink": [{"properties": {
                "show": lit("true"),
                "type": text("PageNavigation"),
                "navigationSection": text(pages_by_id[target["id"]]),
            }}],
        },
    }
    return container(uid(page["id"], "nav", target["id"]), pos, 1000 + i, visual)


def slicer(page, s, i):
    visual = {
        "visualType": "slicer",
        "query": {"queryState": {"Values": {"projections": [proj(s["field"], active=True)]}}},
        "objects": {
            "data": [{"properties": {"mode": text("Dropdown")}}],
            "header": [{"properties": {"show": lit("true"), "fontColor": color(C["muted"]),
                                       "textSize": lit("9D")}}],
            "items": [{"properties": {"fontColor": color(C["text"]), "background": color(C["panel"]),
                                      "textSize": lit("10D")}}],
        },
        "visualContainerObjects": {
            "background": [{"properties": {"show": lit("false")}}],
        },
        "syncGroup": {"groupName": s["id"], "fieldChanges": True, "filterChanges": True},
    }
    pos = {"x": s["x"], "y": s["y"], "w": s["w"], "h": s["h"]}
    return container(uid(page["id"], "slicer", s["id"]), pos, 2000 + i, visual)


def kpi_cards(page):
    row, area = layout["grids"]["kpi_row"], layout["grids"]["main_area"]
    n = len(page["kpis"])
    w = (area["w"] - row["gap"] * (n - 1)) / n
    out = []
    for i, k in enumerate(page["kpis"]):
        box = {"x": area["x"] + i * (w + row["gap"]), "y": row["y"], "w": w, "h": row["h"]}
        pos = {"x": box["x"] + 12, "y": box["y"] + 8, "w": box["w"] - 20, "h": box["h"] - 16}
        label = KPI_LABELS.get(k["measure"], k["measure"])
        visual = {
            "visualType": "card",
            "query": {"queryState": {"Values": {"projections": [proj(f"[{k['measure']}]", display=label)]}}},
            "objects": {
                "labels": [{"properties": {"color": color(C["text"]), "fontSize": lit("20D"),
                                           "fontFamily": text("Segoe UI Semibold")}}],
                "categoryLabels": [{"properties": {"show": lit("true"), "color": color(C["muted"]),
                                                   "fontSize": lit("9D")}}],
            },
        }
        out.append(container(uid(page["id"], "kpi", str(i)), pos, 3000 + i, visual))
    return out


AXES = {
    "categoryAxis": [{"properties": {"showAxisTitle": lit("false"), "labelColor": color(C["muted"])}}],
    "valueAxis": [{"properties": {"showAxisTitle": lit("false"), "labelColor": color(C["muted"]),
                                  "gridlineColor": color(C["border"])}}],
    "legend": [{"properties": {"show": lit("true"), "position": text("Top"),
                               "labelColor": color(C["muted"])}}],
}

ENTREGA_COLORS = {"A Tiempo": C["teal"], "Tardío": C["coral"]}
TIPO_CLIENTE_COLORS = {"Nuevo": C["blue"], "Recurrente": C["amber"]}
BRASIL = {"lat": "-14.5D", "lon": "-52D", "zoom": "2.6D"}


def chart(page_id, slot):
    """Definición (visualType, queryState, sort, objects extra) de cada gráfico, por página/slot."""
    ym = "Calendario[Año-Mes]"
    q = lambda **roles: {r: {"projections": p} for r, p in roles.items()}
    specs = {
        ("resumen", "main"): ("lineChart", q(
            Category=[proj(ym, active=True)], Y=[proj("[Ventas]")], Y2=[proj("[Cantidad Pedidos]", "Pedidos")]),
            sort_by(ym, "Ascending"), {}),
        ("resumen", "side1"): ("azureMap", q(
            Category=[proj("Clientes[Estado]", active=True)], Size=[proj("[Ventas]")]), None, "map"),
        ("resumen", "side2"): ("barChart", q(
            Category=[proj("Productos[Macro Categoría]", active=True)], Y=[proj("[Ventas]")]),
            sort_by("[Ventas]"), {}),

        ("productos", "top"): ("lineClusteredColumnComboChart", q(
            Category=[proj("Productos[Macro Categoría]", active=True)],
            Y=[proj("[Cantidad Pedidos]", "Pedidos")], Y2=[proj("[Ventas]")]),
            sort_by("[Cantidad Pedidos]"), {}),
        ("productos", "bottom1"): ("tableEx", q(
            Values=[proj("Productos[Macro Categoría]", "Macro categoría"),
                    proj("[Cantidad Pedidos]", "Pedidos"),
                    proj("[Ventas]"),
                    proj("[SVG Participación Ventas]", "Participación"),
                    proj("[SVG Puntaje Estrellas]", "Puntaje")]),
            sort_by("[Ventas]"), "table"),
        ("productos", "bottom2"): ("barChart", q(
            Category=[proj("Productos[Categoría]", active=True)], Y=[proj("[Ventas]")]),
            sort_by("[Ventas]"), {}),

        ("logistica", "main"): ("lineChart", q(
            Category=[proj(ym, active=True)],
            Y=[proj("[Días Entrega Promedio]", "Reales"), proj("[Días Entrega Estimados Promedio]", "Estimados")]),
            sort_by(ym, "Ascending"), {}),
        ("logistica", "side1"): ("azureMap", q(
            Category=[proj("Clientes[Estado]", active=True)], Size=[proj("[% Entregas con Retraso]")]), None, "map"),
        ("logistica", "side2"): ("donutChart", q(
            Category=[proj("Items[Categoría Costo Envío]", active=True)], Y=[proj("[Cantidad Ítems]", "Ítems")]),
            None, {}),

        ("clientes", "top"): ("areaChart", q(
            Category=[proj(ym, active=True)], Series=[proj("Clientes[Tipo Cliente]")],
            Y=[proj("[Cantidad Clientes]", "Clientes")]),
            sort_by(ym, "Ascending"), {"dataPoint": series_colors("Clientes[Tipo Cliente]", TIPO_CLIENTE_COLORS)}),
        ("clientes", "bottom1"): ("donutChart", q(
            Category=[proj("Clientes[Frecuencia Compra]", active=True)], Y=[proj("[Cantidad Clientes]", "Clientes")]),
            None, {}),
        ("clientes", "bottom2"): ("barChart", q(
            Category=[proj("Pedidos[Rango Ticket]", active=True)], Y=[proj("[Ventas]")]),
            sort_by("Pedidos[Rango Ticket]", "Ascending"), {}),
        ("clientes", "bottom3"): ("columnChart", q(
            Category=[proj("Items[Categoría Precio]", active=True)], Series=[proj("Pagos[Método Pago]")],
            Y=[proj("[Cantidad Pagos]", "Pagos")]),
            sort_by("Items[Categoría Precio]", "Ascending"), {}),

        ("resenas", "main"): ("clusteredColumnChart", q(
            Category=[proj("Pedidos[Puntaje Reseña]", active=True)], Series=[proj("Pedidos[Estado Entrega]")],
            Y=[proj("[Cantidad Reseñas]", "Reseñas")]),
            sort_by("Pedidos[Puntaje Reseña]", "Ascending"),
            {"dataPoint": series_colors("Pedidos[Estado Entrega]", ENTREGA_COLORS),
             "categoryAxis": [{"properties": {"axisType": text("Categorical"), "showAxisTitle": lit("false"),
                                              "labelColor": color(C["muted"])}}]}),
        ("resenas", "side1"): ("lineChart", q(
            Category=[proj(ym, active=True)], Y=[proj("[Puntaje Promedio]")]),
            sort_by(ym, "Ascending"), {}),
        ("resenas", "side2"): ("scatterChart", q(
            Category=[proj("Clientes[Estado]", active=True)],
            X=[proj("[Días Retraso Promedio]", "Días de retraso")],
            Y=[proj("[Puntaje Promedio]", "Puntaje")],
            Size=[proj("[Cantidad Pedidos]", "Pedidos")]),
            None, {}),
    }
    return specs[(page_id, slot)]


def chart_visual(page, v, i):
    vtype, query_state, sort, extra = chart(page["id"], v["slot"])
    query = {"queryState": query_state}
    if sort:
        query["sortDefinition"] = sort
    if extra == "map":
        objects = {
            "mapControls": [{"properties": {
                "defaultStyle": text("grayscale_dark"), "showStylePicker": lit("false"),
                "showNavigationControls": lit("false"), "showSelectionControl": lit("false"),
                "autoZoom": lit("false"), "zoom": lit(BRASIL["zoom"]),
                "centerLatitude": lit(BRASIL["lat"]), "centerLongitude": lit(BRASIL["lon"])}}],
            "bubbleLayer": [{"properties": {"show": lit("true")}}],
            "dataPoint": [{"properties": {"fill": color(C["blue"])}}],
        }
    elif extra == "table":
        objects = {
            "grid": [{"properties": {"imageHeight": lit("20D"), "rowPadding": lit("4D"),
                                     "gridHorizontal": lit("false"), "gridVertical": lit("false")}}],
            "columnHeaders": [{"properties": {"fontColor": color(C["muted"]), "backColor": color(C["panel"])}}],
            "values": [{"properties": {"fontColorPrimary": color(C["text"]), "backColorPrimary": color(C["panel"]),
                                       "fontColorSecondary": color(C["text"]), "backColorSecondary": color(C["panel"])}}],
            "total": [{"properties": {"totals": lit("false")}}],
        }
    else:
        objects = {**AXES, **extra}
    grid = layout["grids"][page["grid"]]
    pos = inset(grid[v["slot"]], 8)
    visual = {"visualType": vtype, "query": query, "objects": objects}
    return container(uid(page["id"], "chart", v["slot"]), pos, 4000 + i, visual, title=v["title"])


# ---------- página, tema, recursos ----------

def page_json(page, pid):
    bg = f"bg_{page['id']}.png"
    return {
        "$schema": PAGE_SCHEMA,
        "name": pid,
        "displayName": page["name"],
        "displayOption": "FitToPage",
        "height": layout["canvas"]["height"],
        "width": layout["canvas"]["width"],
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
    solid = lambda h: {"solid": {"color": h}}
    return {
        "name": "Olist Dark",
        "dataColors": [C["blue"], C["teal"], C["coral"], C["amber"], C["violet"],
                       "#5AA9FF", "#FF8FA3", "#7BD389", "#C9A7FF", "#FFD27A"],
        "background": C["panel"], "foreground": C["text"], "tableAccent": C["blue"],
        "good": C["teal"], "neutral": C["amber"], "bad": C["coral"],
        "textClasses": {
            "callout": {"fontSize": 20, "fontFace": "Segoe UI Semibold", "color": C["text"]},
            "title": {"fontSize": 11, "fontFace": "Segoe UI Semibold", "color": C["text"]},
            "header": {"fontSize": 11, "fontFace": "Segoe UI Semibold", "color": C["text"]},
            "label": {"fontSize": 9, "fontFace": "Segoe UI", "color": C["muted"]},
        },
        "visualStyles": {
            "*": {"*": {
                "background": [{"show": False}],
                "border": [{"show": False}],
                "dropShadow": [{"show": False}],
                "title": [{"fontColor": solid(C["text"]), "fontSize": 11, "bold": True}],
                "visualHeader": [{"background": solid(C["panel"]), "foreground": solid(C["muted"]),
                                  "border": solid(C["panel"])}],
                "visualTooltip": [{"background": solid(C["rail"]), "titleFontColor": solid(C["muted"]),
                                   "valueFontColor": solid(C["text"])}],
                "categoryAxis": [{"labelColor": solid(C["muted"]), "gridlineShow": False}],
                "valueAxis": [{"labelColor": solid(C["muted"]), "gridlineColor": solid(C["border"])}],
                "legend": [{"labelColor": solid(C["muted"])}],
                "labels": [{"color": solid(C["text"])}],
                "outspacePane": [{"backgroundColor": solid(C["rail"]), "foregroundColor": solid(C["text"]),
                                  "borderColor": solid(C["border"])}],
            }},
            "page": {"*": {"outspace": [{"color": solid(C["bg"])}]}},
            "slicer": {"*": {
                "items": [{"fontColor": solid(C["text"]), "background": solid(C["panel"])}],
                "header": [{"fontColor": solid(C["muted"])}],
            }},
        },
    }


def update_report_json():
    path = DEF / "report.json"
    report = json.loads(path.read_text(encoding="utf-8"))
    custom = report["themeCollection"]["customTheme"]
    custom["name"] = THEME_NAME
    items = [{"name": THEME_NAME, "path": THEME_NAME, "type": "CustomTheme"},
             {"name": LOGO, "path": LOGO, "type": "Image"}]
    items += [{"name": f"bg_{p['id']}.png", "path": f"bg_{p['id']}.png", "type": "Image"}
              for p in layout["pages"]]
    for pkg in report["resourcePackages"]:
        if pkg["name"] == "RegisteredResources":
            pkg["items"] = items
    report.setdefault("objects", {})["outspacePane"] = [{"properties": {
        "expanded": lit("false"), "visible": lit("true")}}]
    path.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")


def write(path, data):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")


def main():
    # Recursos: tema + fondos; se quita el tema viejo
    for old in RES.glob("*.json"):
        if old.name != THEME_NAME:
            old.unlink()
    write(RES / THEME_NAME, theme())
    for p in layout["pages"]:
        shutil.copyfile(DESIGN / "backgrounds" / f"{p['id']}.png", RES / f"bg_{p['id']}.png")
    update_report_json()

    # Páginas y marcadores viejos afuera
    shutil.rmtree(DEF / "pages", ignore_errors=True)
    shutil.rmtree(DEF / "bookmarks", ignore_errors=True)

    pages_by_id = {p["id"]: uid("page", p["id"]) for p in layout["pages"]}
    for page in layout["pages"]:
        pid = pages_by_id[page["id"]]
        pdir = DEF / "pages" / pid
        write(pdir / "page.json", page_json(page, pid))
        visuals = [nav_button(page, t, i, pages_by_id) for i, t in enumerate(layout["pages"])]
        visuals += [slicer(page, s, i) for i, s in enumerate(layout["rail"]["slicers"])]
        visuals += kpi_cards(page)
        visuals += [chart_visual(page, v, i) for i, v in enumerate(page["visuals"])]
        for v in visuals:
            write(pdir / "visuals" / v["name"] / "visual.json", v)
        print(f"{page['name']}: {len(visuals)} visuales")

    write(DEF / "pages" / "pages.json", {
        "$schema": PAGES_SCHEMA,
        "pageOrder": [pages_by_id[p["id"]] for p in layout["pages"]],
        "activePageName": pages_by_id[layout["pages"][0]["id"]],
    })


if __name__ == "__main__":
    main()

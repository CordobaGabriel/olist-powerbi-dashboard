"""Rutas, layout y utilidades compartidas por los scripts de diseño.

`layout.json` es la única fuente de verdad de la paleta y de la geometría de las
páginas: los fondos (build_backgrounds.py), los visuales (build_report.py) y las
medidas SVG (build_model_extras.py) leen de acá para no desincronizarse.
"""
import json
import subprocess
import sys
from pathlib import Path

DESIGN = Path(__file__).resolve().parent
ROOT = DESIGN.parent
REPORT = ROOT / "Olist_Dashboard.Report"
MODEL_TABLES = ROOT / "Olist_Dashboard.SemanticModel" / "definition" / "tables"
BACKGROUNDS = DESIGN / "backgrounds"

LAYOUT = json.loads((DESIGN / "layout.json").read_text(encoding="utf-8"))
PALETTE = LAYOUT["palette"]


def kpi_boxes(page):
    """Rectángulos de las tarjetas KPI de una página, repartidas en el ancho del contenido."""
    ct = LAYOUT["content"]
    n = len(page["kpis"])
    w = (ct["w"] - ct["gap"] * (n - 1)) / n
    return [{"x": ct["x"] + i * (w + ct["gap"]), "y": ct["kpi_y"], "w": w, "h": ct["kpi_h"]}
            for i in range(n)]


def power_bi_running():
    """True si hay una instancia de Power BI Desktop abierta (solo Windows)."""
    if sys.platform != "win32":
        return False
    out = subprocess.run(["tasklist", "/FI", "IMAGENAME eq PBIDesktop.exe", "/NH"],
                         capture_output=True, text=True).stdout
    return "PBIDesktop.exe" in out


def ensure_power_bi_closed(argv=None):
    """Aborta si Power BI Desktop está abierto: guarda el proyecto solo y pisaría lo generado.

    Se puede saltear con --forzar (por ejemplo, al generar sobre una copia del proyecto).
    """
    if "--forzar" in (argv if argv is not None else sys.argv):
        return
    if power_bi_running():
        sys.exit("Power BI Desktop está abierto. Cerralo (sin guardar) antes de generar, "
                 "o usá --forzar si estás trabajando sobre una copia del proyecto.")

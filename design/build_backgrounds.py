"""Genera los fondos de las páginas del reporte a partir de layout.json.

Por cada página escribe backgrounds/<id>.html y lo renderiza a backgrounds/<id>.png
con Microsoft Edge en modo headless. Dibuja solo lo estático: barra lateral,
indicador de la página activa, títulos, etiquetas de las tarjetas KPI y paneles.
Los visuales nativos de Power BI se ubican encima con las mismas coordenadas
(build_report.py).

Uso: python design/build_backgrounds.py
"""
import os
import subprocess
import tempfile
import time
from html import escape
from pathlib import Path

from common import BACKGROUNDS, LAYOUT, PALETTE as C, kpi_boxes

EDGE_CANDIDATES = [
    os.environ.get("EDGE_PATH", ""),
    r"C:\Program Files (x86)\Microsoft\Edge\Application\msedge.exe",
    r"C:\Program Files\Microsoft\Edge\Application\msedge.exe",
]
W, H = LAYOUT["canvas"]["width"], LAYOUT["canvas"]["height"]
CT = LAYOUT["content"]


def find_edge():
    for candidate in EDGE_CANDIDATES:
        if candidate and Path(candidate).is_file():
            return candidate
    raise SystemExit("No se encontró Microsoft Edge. Indicá la ruta con la variable de entorno EDGE_PATH.")


def rect(r, cls, inner=""):
    return (f'<div class="{cls}" style="left:{r["x"]:.1f}px;top:{r["y"]:.1f}px;'
            f'width:{r["w"]:.1f}px;height:{r["h"]:.1f}px">{inner}</div>')


def panel_inner(spec):
    """Texto estático de un panel: conclusión (etiqueta + nota) o título/subtítulo propios."""
    if "insight" in spec:
        inner = f'<span class="plabel">{escape(spec["insight"])}</span>'
        if "note" in spec:
            inner += f'<span class="pnote">{escape(spec["note"])}</span>'
        return inner
    if spec.get("static"):
        return (f'<span class="ptitle">{escape(spec["title"])}</span>'
                f'<span class="psub">{escape(spec["subtitle"])}</span>')
    return ""  # el título lo pone el visual de Power BI


def page_html(page, index):
    rail, nav, foot = LAYOUT["rail"], LAYOUT["rail"]["nav"], LAYOUT["rail"]["footer"]
    active_y = nav["y"] + index * (nav["h"] + nav["gap"])
    tiles = "".join(
        rect(box, "panel", f'<span class="klabel" style="width:{box["w"]:.1f}px">{escape(k["label"])}</span>')
        for box, k in zip(kpi_boxes(page), page["kpis"]))
    grid = LAYOUT["grids"][page["grid"]]
    panels = "".join(rect(grid[slot], "panel", panel_inner(spec)) for slot, spec in page["panels"].items())
    logo, title = rail["logo"], LAYOUT["header"]["title"]
    return f"""<!doctype html>
<html lang="es"><head><meta charset="utf-8"><style>
  * {{ box-sizing: border-box; margin: 0; }}
  body {{ width:{W}px; height:{H}px; overflow:hidden; position:relative;
         background:
           radial-gradient(900px 420px at 92% -12%, #1A2A5A55, transparent 62%),
           radial-gradient(700px 380px at 30% 120%, #12204A40, transparent 60%),
           {C["bg"]};
         font-family: '{LAYOUT["font"]}', 'Segoe UI', sans-serif; color:{C["text"]};
         -webkit-font-smoothing: antialiased; }}
  .rail {{ position:absolute; left:0; top:0; width:{rail["w"]}px; height:{H}px;
           background:{C["rail"]}; border-right:1px solid {C["border"]}; }}
  .logo {{ position:absolute; left:{logo["x"]}px; top:{logo["y"]}px; width:{logo["size"]}px; height:{logo["size"]}px;
           background:#F4F6FB; border-radius:9px; padding:4px; }}
  .brand {{ position:absolute; left:{logo["x"] + logo["size"] + 12}px; top:{logo["y"] + 1}px;
            font-size:16px; font-weight:600; letter-spacing:.1px; line-height:1.15; }}
  .brand small {{ display:block; font-size:10.5px; font-weight:400; color:{C["muted"]}; margin-top:2px; }}
  .active {{ position:absolute; left:{nav["x"]}px; top:{active_y}px; width:{nav["w"]}px; height:{nav["h"]}px;
             border-radius:8px; background:{C["series"][0]}24; }}
  .active::before {{ content:""; position:absolute; left:0; top:10px; bottom:10px; width:3px;
                     border-radius:0 3px 3px 0; background:{C["series"][0]}; }}
  .divider {{ position:absolute; height:1px; background:{C["border"]}; }}
  .note {{ position:absolute; left:12px; width:176px; text-align:center; font-size:10px; color:{C["muted"]};
           line-height:1.4; }}
  .note b {{ color:{C["text2"]}; font-weight:600; }}
  .title {{ position:absolute; left:{title["x"]}px; top:{title["y"]}px; }}
  .title h1 {{ font-size:22px; font-weight:600; letter-spacing:-.2px; line-height:1.2; }}
  .title p {{ font-size:12px; color:{C["muted"]}; margin-top:4px; }}
  .panel {{ position:absolute; background:{C["panel"]}; border:1px solid {C["border"]}; border-radius:12px;
            box-shadow: 0 1px 0 #FFFFFF08 inset, 0 10px 30px #00000038; }}
  .klabel {{ position:absolute; left:0; top:14px; text-align:center; font-size:10px; font-weight:600;
             letter-spacing:.9px; text-transform:uppercase; color:{C["muted"]};
             white-space:nowrap; overflow:hidden; text-overflow:ellipsis; padding:0 10px; }}
  /* textos dibujados acá a la escala de Power BI: 1 pt de Power BI = 1,33 px */
  .plabel {{ position:absolute; left:0; right:0; top:16px; text-align:center; font-size:11px; font-weight:600;
             letter-spacing:.9px; text-transform:uppercase; color:{C["muted"]}; }}
  .pnote {{ position:absolute; left:0; right:0; bottom:18px; text-align:center; font-size:13.5px; color:{C["text2"]}; }}
  .ptitle {{ position:absolute; left:15px; top:13px; font-size:16px; font-weight:600; color:{C["text"]}; }}
  .psub {{ position:absolute; left:15px; top:37px; font-size:12px; color:{C["muted"]}; }}
</style></head><body>
  <div class="rail"></div>
  <img class="logo" src="../assets/olist_logo.png">
  <div class="brand">Olist<small>Tablero de Dirección</small></div>
  <div class="divider" style="left:24px;top:80px;width:152px"></div>
  <div class="active"></div>
  <div class="divider" style="left:24px;top:{foot["y"] - 14}px;width:152px"></div>
  <div class="note" style="top:{foot["y"] + foot["h"] + 2}px">Costos y metas: <b>supuestos</b><br>editables en el modelo</div>
  <div class="title"><h1>{escape(page["title"])}</h1><p>{escape(page["subtitle"])}</p></div>
  <div class="divider" style="left:{CT["x"]}px;top:{CT["kpi_y"] - 10}px;width:{CT["w"]}px;opacity:.6"></div>
  {tiles}
  {panels}
</body></html>"""


def wait_for_file(path, timeout=30):
    """Edge puede devolver el control antes de terminar de escribir la captura:
    espera a que el archivo exista y su tamaño deje de cambiar."""
    last_size, deadline = -1, time.monotonic() + timeout
    while time.monotonic() < deadline:
        size = path.stat().st_size if path.exists() else -1
        if size > 0 and size == last_size:
            return True
        last_size = size
        time.sleep(0.5)
    return False


def render(edge, html_path, png_path, attempts=3):
    """Captura el HTML a PNG. Reintenta porque Edge headless falla de forma intermitente."""
    for attempt in range(1, attempts + 1):
        png_path.unlink(missing_ok=True)
        # perfil nuevo en cada llamada: evita delegar en un Edge ya abierto o chocar con un perfil bloqueado
        with tempfile.TemporaryDirectory(prefix="olist_edge_", ignore_cleanup_errors=True) as profile:
            result = subprocess.run(
                [edge, "--headless=new", "--disable-gpu", "--hide-scrollbars", f"--user-data-dir={profile}",
                 "--force-device-scale-factor=1", f"--window-size={W},{H}", "--virtual-time-budget=3000",
                 f"--screenshot={png_path.resolve()}", html_path.resolve().as_uri()],
                capture_output=True, text=True, timeout=60)
        if wait_for_file(png_path):
            return
        if attempt < attempts:
            time.sleep(3)
    raise RuntimeError(f"Edge no generó {png_path.name}: {result.stderr[-500:]}")


def main():
    edge = find_edge()
    BACKGROUNDS.mkdir(exist_ok=True)
    for old in [*BACKGROUNDS.glob("*.html"), *BACKGROUNDS.glob("*.png")]:
        old.unlink()
    for i, page in enumerate(LAYOUT["pages"]):
        html_path = BACKGROUNDS / f"{page['id']}.html"
        html_path.write_text(page_html(page, i), encoding="utf-8")
        render(edge, html_path, BACKGROUNDS / f"{page['id']}.png")
        print("fondo ok:", page["id"])


if __name__ == "__main__":
    main()

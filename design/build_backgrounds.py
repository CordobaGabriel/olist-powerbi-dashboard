"""Genera los fondos de las páginas del reporte a partir de layout.json.

Por cada página escribe backgrounds/<id>.html y lo renderiza a backgrounds/<id>.png
(1280x720) con Microsoft Edge en modo headless. Dibuja solo lo estático: barra
lateral, indicador de la página activa, títulos, etiquetas de las tarjetas KPI y
paneles. Los visuales nativos de Power BI se ubican encima con las mismas
coordenadas (build_report.py).
"""
import json
import subprocess
import tempfile
import time
from html import escape
from pathlib import Path

ROOT = Path(__file__).parent
OUT = ROOT / "backgrounds"
EDGE = r"C:\Program Files (x86)\Microsoft\Edge\Application\msedge.exe"

layout = json.loads((ROOT / "layout.json").read_text(encoding="utf-8"))
C = layout["palette"]
W, H = layout["canvas"]["width"], layout["canvas"]["height"]
CT = layout["content"]


def kpi_boxes(page):
    n = len(page["kpis"])
    w = (CT["w"] - CT["gap"] * (n - 1)) / n
    return [{"x": CT["x"] + i * (w + CT["gap"]), "y": CT["kpi_y"], "w": w, "h": CT["kpi_h"], **k}
            for i, k in enumerate(page["kpis"])]


def rect(r, cls, inner=""):
    return (f'<div class="{cls}" style="left:{r["x"]:.1f}px;top:{r["y"]:.1f}px;'
            f'width:{r["w"]:.1f}px;height:{r["h"]:.1f}px">{inner}</div>')


def page_html(page, index):
    rail, nav = layout["rail"], layout["rail"]["nav"]
    active_y = nav["y"] + index * (nav["h"] + nav["gap"])
    tiles = []
    for k in kpi_boxes(page):
        label_w = k["w"] * (0.62 if k.get("spark") else 1)
        tiles.append(rect(k, "panel tile",
                          f'<span class="klabel" style="width:{label_w:.1f}px">{escape(k["label"])}</span>'))
    grid = layout["grids"][page["grid"]]
    panels = []
    for slot, spec in page["panels"].items():
        inner = ""
        if "insight" in spec:
            inner = f'<span class="plabel">{escape(spec["insight"])}</span>'
            if "note" in spec:
                inner += f'<span class="pnote">{escape(spec["note"])}</span>'
        elif spec.get("static"):
            inner = (f'<span class="ptitle">{escape(spec["title"])}</span>'
                     f'<span class="psub">{escape(spec["subtitle"])}</span>')
        panels.append(rect(grid[slot], "panel", inner))
    foot = rail["footer"]
    return f"""<!doctype html>
<html lang="es"><head><meta charset="utf-8"><style>
  * {{ box-sizing: border-box; margin: 0; }}
  body {{ width:{W}px; height:{H}px; overflow:hidden; position:relative;
         background:
           radial-gradient(900px 420px at 92% -12%, #1A2A5A55, transparent 62%),
           radial-gradient(700px 380px at 30% 120%, #12204A40, transparent 60%),
           {C["bg"]};
         font-family: '{layout["font"]}', 'Segoe UI', sans-serif; color:{C["text"]};
         -webkit-font-smoothing: antialiased; }}
  .rail {{ position:absolute; left:0; top:0; width:{rail["w"]}px; height:{H}px;
           background:{C["rail"]}; border-right:1px solid {C["border"]}; }}
  .logo {{ position:absolute; left:{rail["logo"]["x"]}px; top:{rail["logo"]["y"]}px;
           width:{rail["logo"]["size"]}px; height:{rail["logo"]["size"]}px;
           background:#F4F6FB; border-radius:9px; padding:4px; }}
  .brand {{ position:absolute; left:{rail["logo"]["x"] + rail["logo"]["size"] + 12}px; top:{rail["logo"]["y"] + 1}px;
            font-size:16px; font-weight:600; letter-spacing:.1px; line-height:1.15; }}
  .brand small {{ display:block; font-size:10.5px; font-weight:400; color:{C["muted"]}; margin-top:2px; }}
  .section {{ position:absolute; left:24px; font-size:9.5px; font-weight:600; letter-spacing:1.4px;
              color:{C["muted"]}; text-transform:uppercase; }}
  .active {{ position:absolute; left:{nav["x"]}px; top:{active_y}px; width:{nav["w"]}px; height:{nav["h"]}px;
             border-radius:8px; background:{C["series"][0]}24; }}
  .active::before {{ content:""; position:absolute; left:0; top:10px; bottom:10px; width:3px;
                     border-radius:0 3px 3px 0; background:{C["series"][0]}; }}
  .divider {{ position:absolute; height:1px; background:{C["border"]}; }}
  .note {{ position:absolute; left:12px; width:176px; text-align:center; font-size:10px; color:{C["muted"]}; line-height:1.4; }}
  .note b {{ color:{C["text2"]}; font-weight:600; }}
  .title {{ position:absolute; left:{layout["header"]["title"]["x"]}px; top:{layout["header"]["title"]["y"]}px; }}
  .title h1 {{ font-size:22px; font-weight:600; letter-spacing:-.2px; line-height:1.2; }}
  .title p {{ font-size:12px; color:{C["muted"]}; margin-top:4px; }}
  .panel {{ position:absolute; background:{C["panel"]}; border:1px solid {C["border"]}; border-radius:12px;
            box-shadow: 0 1px 0 #FFFFFF08 inset, 0 10px 30px #00000038; }}
  .klabel {{ position:absolute; left:0; top:14px; text-align:center; font-size:10px; font-weight:600;
             letter-spacing:.9px; text-transform:uppercase; color:{C["muted"]};
             white-space:nowrap; overflow:hidden; text-overflow:ellipsis; padding:0 10px; }}
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
  <div class="section" style="top:{nav["y"] - 4 - 8}px">&nbsp;</div>
  <div class="active"></div>
  <div class="divider" style="left:24px;top:{foot["y"] - 14}px;width:152px"></div>
  <div class="note" style="top:{foot["y"] + foot["h"] + 2}px">Costos y metas: <b>supuestos</b><br>editables en el modelo</div>
  <div class="title"><h1>{escape(page["title"])}</h1><p>{escape(page["subtitle"])}</p></div>
  <div class="divider" style="left:{CT["x"]}px;top:{CT["kpi_y"] - 10}px;width:{CT["w"]}px;opacity:.6"></div>
  {"".join(tiles)}
  {"".join(panels)}
</body></html>"""


def render(html_path, png_path):
    png_path.unlink(missing_ok=True)
    # perfil propio y nuevo en cada llamada: evita delegar en un Edge ya abierto
    # o chocar con un perfil bloqueado por una corrida anterior
    with tempfile.TemporaryDirectory(prefix="olist_edge_", ignore_cleanup_errors=True) as profile:
        result = subprocess.run(
            [EDGE, "--headless=new", "--disable-gpu", "--hide-scrollbars",
             f"--user-data-dir={profile}",
             "--force-device-scale-factor=1", f"--window-size={W},{H}",
             "--virtual-time-budget=3000",
             f"--screenshot={png_path.resolve()}", html_path.resolve().as_uri()],
            capture_output=True, text=True, timeout=60)
    # Edge puede devolver el control antes de terminar de escribir la captura
    last_size = -1
    for _ in range(60):
        if png_path.exists() and png_path.stat().st_size == last_size > 0:
            return
        last_size = png_path.stat().st_size if png_path.exists() else -1
        time.sleep(0.5)
    raise RuntimeError(f"Edge no generó {png_path.name}: {result.stderr[-500:]}")


if __name__ == "__main__":
    OUT.mkdir(exist_ok=True)
    for old in OUT.glob("*"):
        old.unlink()
    for i, page in enumerate(layout["pages"]):
        html_path = OUT / f"{page['id']}.html"
        html_path.write_text(page_html(page, i), encoding="utf-8")
        for intento in range(3):  # Edge headless falla de forma intermitente
            try:
                render(html_path, OUT / f"{page['id']}.png")
                break
            except RuntimeError:
                if intento == 2:
                    raise
                time.sleep(3)
        print("ok", page["id"])

"""Genera los fondos de las páginas del reporte a partir de layout.json.

Por cada página escribe backgrounds/<id>.html y lo renderiza a backgrounds/<id>.png
(1280x720) con Microsoft Edge en modo headless. Los visuales nativos de Power BI
se ubican después exactamente sobre los paneles dibujados acá, con las mismas
coordenadas del layout.
"""
import json
import subprocess
import tempfile
from pathlib import Path

ROOT = Path(__file__).parent
OUT = ROOT / "backgrounds"
EDGE = r"C:\Program Files (x86)\Microsoft\Edge\Application\msedge.exe"

layout = json.loads((ROOT / "layout.json").read_text(encoding="utf-8"))
C = layout["palette"]
W, H = layout["canvas"]["width"], layout["canvas"]["height"]


def box(r, cls, extra=""):
    return (f'<div class="{cls}" style="left:{r["x"]}px;top:{r["y"]}px;'
            f'width:{r["w"]}px;height:{r["h"]}px;{extra}"></div>')


def kpi_boxes(page):
    row = layout["grids"]["kpi_row"]
    area = layout["grids"]["main_area"]
    n = len(page["kpis"])
    w = (area["w"] - row["gap"] * (n - 1)) / n
    html = []
    for i, k in enumerate(page["kpis"]):
        x = area["x"] + i * (w + row["gap"])
        color = C[k["accent"]]
        html.append(
            f'<div class="kpi" style="left:{x:.1f}px;top:{row["y"]}px;width:{w:.1f}px;height:{row["h"]}px;">'
            f'<span class="accent" style="background:{color};box-shadow:0 0 14px {color}88"></span>'
            f'<span class="glow" style="background:radial-gradient(circle at 100% 0%, {color}22, transparent 60%)"></span>'
            f'</div>')
    return "".join(html)


def page_html(page):
    grid = layout["grids"][page["grid"]]
    rail = layout["rail"]
    panels = "".join(box(grid[v["slot"]], "panel") for v in page["visuals"])
    return f"""<!doctype html>
<html><head><meta charset="utf-8"><style>
  @import url('https://fonts.googleapis.com/css2?family=Inter:wght@400;600;700&display=swap');
  * {{ box-sizing: border-box; margin: 0; }}
  body {{ width:{W}px; height:{H}px; overflow:hidden; position:relative;
         background: radial-gradient(1200px 600px at 85% -10%, #16245080, transparent 60%), {C["bg"]};
         font-family: 'Inter', 'Segoe UI', sans-serif; color:{C["text"]}; }}
  .rail {{ position:absolute; background:{C["rail"]}; border-right:1px solid {C["border"]}; }}
  .panel, .kpi {{ position:absolute; background:{C["panel"]}; border:1px solid {C["border"]};
                  border-radius:14px; box-shadow: 0 8px 24px #00000040; overflow:hidden; }}
  .kpi .accent {{ position:absolute; left:0; top:18px; bottom:18px; width:4px; border-radius:0 4px 4px 0; }}
  .kpi .glow {{ position:absolute; inset:0; }}
  .logo {{ position:absolute; background:#F4F6FB; border-radius:10px; padding:4px; }}
  .brand {{ position:absolute; left:70px; top:22px; font-weight:700; font-size:20px; letter-spacing:.2px; }}
  .brand small {{ display:block; font-weight:400; font-size:11px; color:{C["muted"]}; letter-spacing:.3px; }}
  .label {{ position:absolute; left:24px; font-size:10px; font-weight:600; letter-spacing:1.4px; color:{C["muted"]}; }}
  .divider {{ position:absolute; left:20px; width:160px; height:1px; background:{C["border"]}; }}
  .title {{ position:absolute; left:{layout["header"]["x"]}px; top:{layout["header"]["y"]}px; }}
  .title h1 {{ font-size:24px; font-weight:700; line-height:1.1; }}
  .title p {{ font-size:12px; color:{C["muted"]}; margin-top:6px; }}
  .source {{ position:absolute; right:16px; top:30px; font-size:10px; color:{C["muted"]}; }}
</style></head><body>
  {box(rail, "rail")}
  <img class="logo" src="../assets/olist_logo.png" style="left:{rail["logo"]["x"]}px;top:{rail["logo"]["y"]}px;width:{rail["logo"]["w"]}px;height:{rail["logo"]["h"]}px;">
  <div class="brand">Olist<small>E-commerce Analytics</small></div>
  <div class="divider" style="top:76px"></div>
  <div class="label" style="top:{rail["nav"]["y"] - 4}px">&nbsp;</div>
  <div class="divider" style="top:{rail["filters_label_y"] - 12}px"></div>
  <div class="label" style="top:{rail["filters_label_y"]}px">FILTROS</div>
  <div class="title"><h1>{page["name"]}</h1><p>{page["subtitle"]}</p></div>
  <div class="source">Fuente: Olist Brazilian E-Commerce (Kaggle)</div>
  {kpi_boxes(page)}
  {panels}
</body></html>"""


def render(html_path, png_path):
    subprocess.run(
        [EDGE, "--headless=new", "--disable-gpu", "--hide-scrollbars",
         # perfil propio: evita que la llamada se delegue a un Edge ya abierto
         f"--user-data-dir={Path(tempfile.gettempdir()) / 'olist_edge_render'}",
         "--force-device-scale-factor=1", f"--window-size={W},{H}",
         "--virtual-time-budget=3000",
         f"--screenshot={png_path.resolve()}", html_path.resolve().as_uri()],
        check=True, capture_output=True, timeout=60)


if __name__ == "__main__":
    OUT.mkdir(exist_ok=True)
    for page in layout["pages"]:
        html_path = OUT / f"{page['id']}.html"
        html_path.write_text(page_html(page), encoding="utf-8")
        render(html_path, OUT / f"{page['id']}.png")
        print("ok", page["id"])

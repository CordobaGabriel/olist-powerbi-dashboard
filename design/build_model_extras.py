"""Agrega al modelo TMDL las medidas generadas por patrón.

- Por cada KPI: '<KPI> AA' (año anterior, cortado en la última fecha con datos),
  'Δ <KPI> Flecha' (▲/▼, se colorea con 'Δ <KPI> Color') y 'Δ <KPI> Texto'.
- Medidas SVG para tablas y matrices (cumplimiento de meta, retención de cohortes,
  barra de margen, estrellas de vendedores).
- Columnas con formato para las tablas calculadas de parámetros.

Es idempotente: antes de escribir borra los bloques que genera. Correr con Power BI
Desktop cerrado y después abrir el .pbip.
"""
import re
from pathlib import Path

TABLES = Path(__file__).parent.parent / "Olist_Dashboard.SemanticModel" / "definition" / "tables"
MEDIDAS = TABLES / "Medidas.tmdl"

GOOD, WARNING, CRITICAL, MUTED = "#0CA30C", "#FAB219", "#D03B3B", "#8A96B3"
# Para texto sobre el fondo oscuro se usa 'serious' (6,6:1) en lugar de 'critical' (3,3:1)
TEXT_BAD = "#EC835A"

# (medida, tipo de variación, mejor si sube)
KPIS = [
    ("Ventas", "pct", True),
    ("Ingresos Productos", "pct", True),
    ("Margen Contribución", "pct", True),
    ("% Margen Contribución", "pp", True),
    ("Ticket Medio", "pct", True),
    ("Cantidad Pedidos", "pct", True),
    ("Cantidad Clientes", "pct", True),
    ("% Clientes Recurrentes", "pp", True),
    ("Ventas por Cliente", "pct", True),
    ("Margen por Cliente", "pct", True),
    ("% Entregas con Retraso", "pp", False),
    ("Días Entrega Promedio", "dias", False),
    ("Días Despacho Vendedor", "dias", False),
    ("Días Tránsito", "dias", False),
    ("Costo Envío % Ventas", "pp", False),
    ("Puntaje Promedio", "puntos", True),
    ("% Reseñas Positivas (4-5)", "pp", True),
    ("Cantidad Reseñas", "pct", True),
]

FORMAT_ANTERIOR = {"pct": None, "pp": "0.0%", "dias": "0.0", "puntos": "0.00"}


def q(name):
    return "'" + name.replace("'", "''") + "'"


def measure(name, expr, folder, fmt=None, hidden=False, description=None, data_category=None):
    lines = []
    if description:
        lines.append(f"\t/// {description}")
    body = expr.strip().splitlines()
    if len(body) == 1:
        lines.append(f"\tmeasure {q(name)} = {body[0]}")
    else:
        lines.append(f"\tmeasure {q(name)} =")
        lines += ["\t\t\t" + b for b in body]
    if fmt:
        lines.append(f"\t\tformatString: {fmt}")
    if hidden:
        lines.append("\t\tisHidden")
    if data_category:
        lines.append(f"\t\tdataCategory: {data_category}")
    lines.append(f"\t\tdisplayFolder: {folder}")
    return "\n".join(lines)


def delta_measures(kpi, kind, up):
    out = []
    aa = f"{kpi} AA"
    if kpi != "Ventas":  # 'Ventas AA' ya existe en el modelo
        out.append(measure(aa, f"""
VAR UltimaFecha = [Última Fecha Datos]
RETURN
    CALCULATE(
        [{kpi}],
        SAMEPERIODLASTYEAR( FILTER( VALUES( Calendario[Fecha] ), Calendario[Fecha] <= UltimaFecha ) )
    )""", "8. Comparaciones", FORMAT_ANTERIOR[kind] or "#,0",
            description=f"{kpi} del mismo período del año anterior, cortado en la última fecha con datos."))
    delta = "DIVIDE( Actual - Anterior, Anterior )" if kind == "pct" else "Actual - Anterior"
    valor = {
        "pct": 'FORMAT( ABS( Delta ), "0.0%" )',
        "pp": 'FORMAT( ABS( Delta ) * 100, "0.0" ) & " pp"',
        "dias": 'FORMAT( ABS( Delta ), "0.0" ) & " días"',
        "puntos": 'FORMAT( ABS( Delta ), "0.00" ) & " pts"',
    }[kind]
    head = f"""
VAR Actual = [{kpi}]
VAR Anterior = [{aa}]
VAR Delta = {delta}"""
    out.append(measure(f"Δ {kpi} Flecha", head + """
RETURN
    IF(
        ISBLANK( Actual ) || ISBLANK( Anterior ),
        "●",
        IF( Delta > 0, "▲", IF( Delta < 0, "▼", "●" ) )
    )""", "8. Comparaciones"))
    out.append(measure(f"Δ {kpi} Texto", head + f"""
RETURN
    IF(
        ISBLANK( Actual ) || ISBLANK( Anterior ),
        "sin dato del año anterior",
        {valor} & " vs. año anterior"
    )""", "8. Comparaciones"))
    bueno, malo = ("Delta > 0", "Delta < 0") if up else ("Delta < 0", "Delta > 0")
    out.append(measure(f"Δ {kpi} Color", head + f"""
RETURN
    SWITCH(
        TRUE(),
        ISBLANK( Actual ) || ISBLANK( Anterior ), "{MUTED}",
        {bueno}, "{GOOD}",
        {malo}, "{TEXT_BAD}",
        "{MUTED}"
    )""", "8. Comparaciones", hidden=True))
    return out


def status_color(expr, bad=CRITICAL):
    return f"""SWITCH( TRUE(), ISBLANK( {expr} ), "{MUTED}", {expr} >= 1, "{GOOD}", {expr} >= 0.9, "{WARNING}", "{bad}" )"""


OTHER = [
    measure("Texto Fecha Datos", '"Datos al " & FORMAT( [Última Fecha Datos], "dd/mm/yyyy" )', "0. Auxiliares"),
    measure("Retención Cohorte", """
VAR Mes = SELECTEDVALUE( 'Meses de Vida'[Mes de Vida] )
VAR UltimaFecha = [Última Fecha Datos]
VAR InicioCohorte = EOMONTH( MIN( Clientes[Fecha Primera Compra] ), -1 ) + 1
VAR Base = COUNTROWS( Clientes )
VAR Activos =
    IF(
        Mes = 0,
        Base,
        CALCULATE(
            COUNTROWS( Recompras ),
            TREATAS( VALUES( Clientes[ID Cliente] ), Recompras[ID Cliente] ),
            Recompras[Mes de Vida] = Mes
        )
    )
RETURN
    -- cohortes con menos de 30 clientes no son representativas
    IF(
        NOT ISBLANK( Mes ) && Base >= 30 && EOMONTH( InicioCohorte, Mes ) <= EOMONTH( UltimaFecha, 0 ),
        DIVIDE( Activos, Base )
    )""", "3. Clientes", fmt="0.0%",
            description="% de clientes de la cohorte que volvieron a comprar N meses después de su primera compra."),
    measure("Texto Meta Anual", '"Meta anual: " & FORMAT( [Meta Ventas Plan] / 1000000, "R$ #,0.0" ) & " M"',
            "9. Metas y Proyección"),
    measure("Meta Ventas Flecha", 'IF( ISBLANK( [Cumplimiento Meta] ), "●", "◆" )', "9. Metas y Proyección"),
    measure("Meta Ventas Texto", """
VAR C = [Cumplimiento Meta]
RETURN
    IF( ISBLANK( C ), "sin meta para el período", FORMAT( C, "0%" ) & " de la meta" )""", "9. Metas y Proyección"),
    measure("Meta Ventas Color", status_color("[Cumplimiento Meta]", TEXT_BAD), "9. Metas y Proyección", hidden=True),
    measure("Cumplimiento Proyectado Color", status_color("[Cumplimiento Proyectado]", TEXT_BAD), "9. Metas y Proyección",
            hidden=True),
    measure("Cumplimiento Proyectado Texto", """
VAR C = [Cumplimiento Proyectado]
RETURN
    IF( ISBLANK( C ), "sin meta", FORMAT( C, "0%" ) & " de la meta anual" )""", "9. Metas y Proyección"),
    measure("SVG Cumplimiento Meta", f"""
VAR C = [Cumplimiento Meta]
-- ancho con 3 dígitos: ordenar la columna alfabéticamente equivale a ordenar por cumplimiento
VAR Ancho = FORMAT( ROUND( MIN( C, 1.5 ) / 1.5 * 95, 0 ), "000" )
VAR Color = SUBSTITUTE( {status_color("C")}, "#", "%23" )
VAR Texto = SUBSTITUTE( FORMAT( C, "0%" ), "%", "%25" )
RETURN
    IF(
        NOT ISBLANK( C ),
        "data:image/svg+xml;utf8,<svg xmlns='http://www.w3.org/2000/svg' width='140' height='20'>"
            & "<rect x='0' y='6' width='95' height='8' rx='4' fill='%231F2B4D'/>"
            & "<rect x='0' y='6' width='" & Ancho & "' height='8' rx='4' fill='" & Color & "'/>"
            & "<rect x='62.3' y='2' width='2' height='16' rx='1' fill='%23E6EAF2'/>"
            & "<text x='103' y='14' font-family='Segoe UI' font-size='11' fill='%23E6EAF2'>" & Texto & "</text></svg>"
    )""", "6. Visuales SVG", data_category="ImageUrl",
            description="Bala de cumplimiento de meta: barra = cumplimiento (0-150 %), marca blanca = 100 %."),
    measure("SVG Retención", """
VAR R = [Retención Cohorte]
VAR Mes = SELECTEDVALUE( 'Meses de Vida'[Mes de Vida] )
VAR Intensidad = IF( Mes = 0, 0, MIN( R / 0.01, 1 ) )
VAR Texto = SUBSTITUTE( FORMAT( R, IF( Mes = 0, "0%", "0.0%" ) ), "%", "%25" )
RETURN
    IF(
        NOT ISBLANK( R ),
        "data:image/svg+xml;utf8,<svg xmlns='http://www.w3.org/2000/svg' width='58' height='22'>"
            & "<rect x='1' y='1' width='56' height='20' rx='3' fill='%23172243'/>"
            & "<rect x='1' y='1' width='56' height='20' rx='3' fill='%233B78F0' fill-opacity='"
            & SUBSTITUTE( FORMAT( Intensidad, "0.00" ), ",", "." ) & "'/>"
            & "<text x='29' y='15' text-anchor='middle' font-family='Segoe UI' font-size='10' fill='%23E6EAF2'>"
            & Texto & "</text></svg>"
    )""", "6. Visuales SVG", data_category="ImageUrl",
            description="Celda de mapa de calor: intensidad azul según la retención (escala 0-1 %, saturada arriba)."),
    measure("SVG Barra Margen", """
VAR M = [Margen Contribución]
VAR Maximo = MAXX( ALLSELECTED( Productos[Categoría] ), [Margen Contribución] )
VAR Ancho = MAX( ROUND( DIVIDE( M, Maximo ) * 80, 0 ), 1 )
VAR Clase = [Clase ABC]
VAR Color = SWITCH( Clase, "A", "%233B78F0", "B", "%232C5AB5", "%23344266" )
VAR Texto = SUBSTITUTE( FORMAT( [% Acumulado Margen], "0%" ), "%", "%25" )
RETURN
    IF(
        ISINSCOPE( Productos[Categoría] ) && NOT ISBLANK( M ),
        "data:image/svg+xml;utf8,<svg xmlns='http://www.w3.org/2000/svg' width='150' height='20'>"
            & "<rect x='0' y='6' width='" & Ancho & "' height='8' rx='4' fill='" & Color & "'/>"
            & "<text x='88' y='14' font-family='Segoe UI' font-size='10.5' fill='%238A96B3'>acum. " & Texto & "</text></svg>"
    )""", "6. Visuales SVG", data_category="ImageUrl",
            description="Barra de margen por categoría (color por clase ABC) con el % acumulado del Pareto."),
    measure("SVG Estrellas Compactas", """
VAR Puntaje = [Puntaje Promedio]
VAR Ancho = ROUND( DIVIDE( Puntaje, 5 ) * 84, 0 )
VAR Fila =
    "<use xlink:href='%23e'/><use xlink:href='%23e' x='17'/><use xlink:href='%23e' x='34'/>"
        & "<use xlink:href='%23e' x='51'/><use xlink:href='%23e' x='68'/>"
RETURN
    IF(
        NOT ISBLANK( Puntaje ),
        "data:image/svg+xml;utf8,<svg xmlns='http://www.w3.org/2000/svg' xmlns:xlink='http://www.w3.org/1999/xlink' width='86' height='18'>"
            & "<defs><polygon id='e' points='8,1 10,6 15.5,6 11,9.5 12.8,15 8,11.8 3.2,15 5,9.5 0.5,6 6,6'/>"
            & "<clipPath id='c'><rect width='" & Ancho & "' height='18'/></clipPath></defs>"
            & "<g fill='%232A3658'>" & Fila & "</g>"
            & "<g fill='%23F5B83D' clip-path='url(%23c)'>" & Fila & "</g></svg>"
    )""", "6. Visuales SVG", data_category="ImageUrl",
            description="Cinco estrellas sin el número, para columnas angostas."),
    measure("SVG Puntaje Vendedor", "IF( [Cantidad Pedidos] >= 50, [SVG Estrellas Compactas] )", "6. Visuales SVG",
            data_category="ImageUrl"),
]

PARAM_COLUMNS = {
    "Crecimiento Objetivo": [("Crecimiento Objetivo", "double", "0%")],
    "Reducción Retrasos": [("Reducción Retrasos", "double", "0%")],
    "Supuestos Costos": [("Macro Categoría", "string", None), ("% Costo Mercadería", "double", "0%")],
    "Meses de Vida": [("Mes de Vida", "int64", "0")],
}


def generated_names():
    names = []
    for kpi, _, _ in KPIS:
        if kpi != "Ventas":
            names.append(f"{kpi} AA")
        names += [f"Δ {kpi} Flecha", f"Δ {kpi} Texto", f"Δ {kpi} Color"]
    names += [re.match(r"(?:\t///.*\n)?\tmeasure '((?:[^']|'')+)'", m).group(1).replace("''", "'") for m in OTHER]
    return names


def strip_measures(text, names):
    """Quita los bloques 'measure' (con su descripción ///) cuyos nombres se regeneran."""
    lines = text.split("\n")
    out, i = [], 0
    targets = {q(n) for n in names}
    while i < len(lines):
        line = lines[i].rstrip("\r")
        start = i
        while line.startswith("\t///") and i + 1 < len(lines):
            i += 1
            line = lines[i].rstrip("\r")
        m = re.match(r"\tmeasure ('(?:[^']|'')+'|[^\s=]+)", line)
        if m and m.group(1) in targets:
            i += 1
            while i < len(lines) and (lines[i].startswith("\t\t") or lines[i].strip() == ""):
                i += 1
            continue
        out.extend(lines[start:i + 1])
        i += 1
    return "\n".join(out)


def add_param_columns():
    for table, cols in PARAM_COLUMNS.items():
        path = TABLES / f"{table}.tmdl"
        text = path.read_text(encoding="utf-8")
        text = re.sub(r"(?m)^\tcolumn [^\n]*\n(?:\t\t[^\n]*\n|\r?\n)*", "", text)
        block = ""
        for name, dtype, fmt in cols:
            block += f"\tcolumn {q(name)}\n\t\tdataType: {dtype}\n"
            if fmt:
                block += f"\t\tformatString: {fmt}\n"
            block += f"\t\tsummarizeBy: none\n\t\tisNameInferred\n\t\tsourceColumn: [{name}]\n\n"
        text = text.replace("\tpartition ", block + "\tpartition ", 1)
        path.write_text(text, encoding="utf-8")


def main():
    text = MEDIDAS.read_text(encoding="utf-8")
    text = strip_measures(text, generated_names())
    # colores de marca validados (paleta oscura)
    text = text.replace("%232F6BFF", "%233B78F0")
    blocks = []
    for kpi, kind, up in KPIS:
        blocks += delta_measures(kpi, kind, up)
    blocks += OTHER
    insert = "\n\n".join(blocks) + "\n\n"
    marker = "\tcolumn Oculta"
    assert marker in text, "no se encontró la columna Oculta en Medidas.tmdl"
    text = text.replace(marker, insert + marker, 1)
    MEDIDAS.write_text(text, encoding="utf-8")
    add_param_columns()
    print(f"medidas generadas: {len(blocks)}")


if __name__ == "__main__":
    main()

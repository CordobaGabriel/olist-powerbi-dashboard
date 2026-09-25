"""Agrega al modelo TMDL las medidas que siguen un patrón.

- Por cada KPI: '<KPI> AA' (mismo período del año anterior, cortado en la última
  fecha con datos), 'Δ <KPI> Texto' y 'Δ <KPI> Color' (formato condicional).
- Textos y colores de meta/proyección, retención de cohortes y medidas SVG para
  tablas y matrices (cumplimiento de meta, mapa de calor, barra de margen, estrellas).
- Columnas con formato para las tablas calculadas de parámetros.

Es idempotente: antes de escribir borra los bloques que genera (y los que generaba
en versiones anteriores). Los colores salen de layout.json.

Uso: python design/build_model_extras.py   (con Power BI Desktop cerrado)
"""
import re

from common import MODEL_TABLES, PALETTE as P, ensure_power_bi_closed

MEDIDAS = MODEL_TABLES / "Medidas.tmdl"

GOOD, WARNING, CRITICAL, MUTED = P["good"], P["warning"], P["critical"], P["muted"]
# Texto negativo sobre fondo oscuro: 'serious' (6,6:1) se lee mejor que 'critical' (3,3:1)
TEXT_BAD = P["serious"]
STAR_ON, STAR_OFF = "#F5B83D", "#2A3658"
ABC_RAMP = {"A": P["series"][0], "B": "#2C5AB5", "C": "#344266"}  # rampa ordinal azul

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
FORMAT_AA = {"pct": "#,0", "pp": "0.0%", "dias": "0.0", "puntos": "0.00"}
DELTA_TEXT = {
    "pct": 'FORMAT( ABS( Delta ), "0.0%" )',
    "pp": 'FORMAT( ABS( Delta ) * 100, "0.0" ) & " pp"',
    "dias": 'FORMAT( ABS( Delta ), "0.0" ) & " días"',
    "puntos": 'FORMAT( ABS( Delta ), "0.00" ) & " pts"',
}
# Medidas que generaban versiones anteriores de este script y ya no se usan
LEGACY = [f"Δ {kpi} Flecha" for kpi, _, _ in KPIS] + ["Meta Ventas Flecha"]


def q(name):
    """Nombre de objeto TMDL entre comillas simples."""
    return "'" + name.replace("'", "''") + "'"


def svg(hex_color):
    """Color para una URL de datos SVG: '#' tiene que ir escapado."""
    return hex_color.replace("#", "%23")


def measure(name, expr, folder, fmt=None, hidden=False, description=None, data_category=None):
    """Devuelve (nombre, bloque TMDL) de una medida de la tabla Medidas."""
    lines = [f"\t/// {description}"] if description else []
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
    return name, "\n".join(lines)


def status_color(expr, bad=CRITICAL):
    """Semáforo de cumplimiento: >= 100 % bien, >= 90 % alerta, menos: mal."""
    return (f'SWITCH( TRUE(), ISBLANK( {expr} ), "{MUTED}", {expr} >= 1, "{GOOD}", '
            f'{expr} >= 0.9, "{WARNING}", "{bad}" )')


def delta_measures(kpi, kind, up):
    """Año anterior + texto y color de la variación de un KPI."""
    out = []
    aa = f"{kpi} AA"
    if kpi != "Ventas":  # 'Ventas AA' está en el modelo (la usan meta y proyección)
        out.append(measure(aa, f"""
VAR UltimaFecha = [Última Fecha Datos]
RETURN
    CALCULATE(
        [{kpi}],
        SAMEPERIODLASTYEAR( FILTER( VALUES( Calendario[Fecha] ), Calendario[Fecha] <= UltimaFecha ) )
    )""", "8. Comparaciones", FORMAT_AA[kind],
            description=f"{kpi} del mismo período del año anterior, cortado en la última fecha con datos."))
    delta = "DIVIDE( Actual - Anterior, Anterior )" if kind == "pct" else "Actual - Anterior"
    head = f"""
VAR Actual = [{kpi}]
VAR Anterior = [{aa}]
VAR Delta = {delta}"""
    out.append(measure(f"Δ {kpi} Texto", head + f"""
RETURN
    IF(
        ISBLANK( Actual ) || ISBLANK( Anterior ),
        "sin dato del año anterior",
        IF( Delta > 0, "▲ ", IF( Delta < 0, "▼ ", "" ) ) & {DELTA_TEXT[kind]} & " vs. año anterior"
    )""", "8. Comparaciones"))
    good, bad = ("Delta > 0", "Delta < 0") if up else ("Delta < 0", "Delta > 0")
    out.append(measure(f"Δ {kpi} Color", head + f"""
RETURN
    SWITCH(
        TRUE(),
        ISBLANK( Actual ) || ISBLANK( Anterior ), "{MUTED}",
        {good}, "{GOOD}",
        {bad}, "{TEXT_BAD}",
        "{MUTED}"
    )""", "8. Comparaciones", hidden=True))
    return out


def stars_svg(width):
    """Cinco estrellas rellenas proporcionalmente al puntaje (variable DAX 'Puntaje')."""
    row = ("\"<use xlink:href='%23e'/><use xlink:href='%23e' x='17'/><use xlink:href='%23e' x='34'/>\"\n"
           "        & \"<use xlink:href='%23e' x='51'/><use xlink:href='%23e' x='68'/>\"")
    return f"""
VAR Puntaje = [Puntaje Promedio]
VAR Ancho = ROUND( DIVIDE( Puntaje, 5 ) * 84, 0 )
VAR Fila =
    {row}
RETURN
    IF(
        NOT ISBLANK( Puntaje ),
        "data:image/svg+xml;utf8,<svg xmlns='http://www.w3.org/2000/svg' xmlns:xlink='http://www.w3.org/1999/xlink' width='{width}' height='18'>"
            & "<defs><polygon id='e' points='8,1 10,6 15.5,6 11,9.5 12.8,15 8,11.8 3.2,15 5,9.5 0.5,6 6,6'/>"
            & "<clipPath id='c'><rect width='" & Ancho & "' height='18'/></clipPath></defs>"
            & "<g fill='{svg(STAR_OFF)}'>" & Fila & "</g>"
            & "<g fill='{svg(STAR_ON)}' clip-path='url(%23c)'>" & Fila & "</g></svg>"
    )"""


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
    measure("Meta Ventas Texto", """
VAR C = [Cumplimiento Meta]
RETURN
    IF( ISBLANK( C ), "sin meta para el período", FORMAT( C, "0%" ) & " de la meta" )""", "9. Metas y Proyección"),
    measure("Meta Ventas Color", status_color("[Cumplimiento Meta]", TEXT_BAD), "9. Metas y Proyección", hidden=True),
    measure("Cumplimiento Proyectado Texto", """
VAR C = [Cumplimiento Proyectado]
RETURN
    IF( ISBLANK( C ), "sin meta", FORMAT( C, "0%" ) & " de la meta anual" )""", "9. Metas y Proyección"),
    measure("Cumplimiento Proyectado Color", status_color("[Cumplimiento Proyectado]", TEXT_BAD),
            "9. Metas y Proyección", hidden=True),
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
            & "<rect x='0' y='6' width='95' height='8' rx='4' fill='{svg(P["border"])}'/>"
            & "<rect x='0' y='6' width='" & Ancho & "' height='8' rx='4' fill='" & Color & "'/>"
            & "<rect x='62.3' y='2' width='2' height='16' rx='1' fill='{svg(P["text"])}'/>"
            & "<text x='103' y='14' font-family='Segoe UI' font-size='11' fill='{svg(P["text"])}'>" & Texto & "</text></svg>"
    )""", "6. Visuales SVG", data_category="ImageUrl",
            description="Bala de cumplimiento de meta: barra = cumplimiento (0-150 %), marca blanca = 100 %."),
    measure("SVG Retención", f"""
VAR R = [Retención Cohorte]
VAR Mes = SELECTEDVALUE( 'Meses de Vida'[Mes de Vida] )
VAR Intensidad = IF( Mes = 0, 0, MIN( R / 0.01, 1 ) )
VAR Texto = SUBSTITUTE( FORMAT( R, IF( Mes = 0, "0%", "0.0%" ) ), "%", "%25" )
RETURN
    IF(
        NOT ISBLANK( R ),
        "data:image/svg+xml;utf8,<svg xmlns='http://www.w3.org/2000/svg' width='58' height='22'>"
            & "<rect x='1' y='1' width='56' height='20' rx='3' fill='{svg(P["panel_hi"])}'/>"
            & "<rect x='1' y='1' width='56' height='20' rx='3' fill='{svg(P["series"][0])}' fill-opacity='"
            & SUBSTITUTE( FORMAT( Intensidad, "0.00" ), ",", "." ) & "'/>"
            & "<text x='29' y='15' text-anchor='middle' font-family='Segoe UI' font-size='10' fill='{svg(P["text"])}'>"
            & Texto & "</text></svg>"
    )""", "6. Visuales SVG", data_category="ImageUrl",
            description="Celda de mapa de calor: intensidad azul según la retención (escala 0-1 %, saturada arriba)."),
    measure("SVG Barra Margen", f"""
VAR M = [Margen Contribución]
VAR Maximo = MAXX( ALLSELECTED( Productos[Categoría] ), [Margen Contribución] )
VAR Ancho = MAX( ROUND( DIVIDE( M, Maximo ) * 80, 0 ), 1 )
VAR Color = SWITCH( [Clase ABC], "A", "{svg(ABC_RAMP["A"])}", "B", "{svg(ABC_RAMP["B"])}", "{svg(ABC_RAMP["C"])}" )
VAR Texto = SUBSTITUTE( FORMAT( [% Acumulado Margen], "0%" ), "%", "%25" )
RETURN
    IF(
        ISINSCOPE( Productos[Categoría] ) && NOT ISBLANK( M ),
        "data:image/svg+xml;utf8,<svg xmlns='http://www.w3.org/2000/svg' width='150' height='20'>"
            & "<rect x='0' y='6' width='" & Ancho & "' height='8' rx='4' fill='" & Color & "'/>"
            & "<text x='88' y='14' font-family='Segoe UI' font-size='10.5' fill='{svg(P["muted"])}'>acum. " & Texto & "</text></svg>"
    )""", "6. Visuales SVG", data_category="ImageUrl",
            description="Barra de margen por categoría (color por clase ABC) con el % acumulado del Pareto."),
    measure("SVG Estrellas Compactas", stars_svg(86), "6. Visuales SVG", data_category="ImageUrl",
            description="Cinco estrellas sin el número, para columnas angostas."),
    measure("SVG Puntaje Vendedor", "IF( [Cantidad Pedidos] >= 50, [SVG Estrellas Compactas] )", "6. Visuales SVG",
            data_category="ImageUrl", description="Estrellas solo para vendedores con muestra representativa."),
]

PARAM_COLUMNS = {
    "Crecimiento Objetivo": [("Crecimiento Objetivo", "double", "0%")],
    "Reducción Retrasos": [("Reducción Retrasos", "double", "0%")],
    "Supuestos Costos": [("Macro Categoría", "string", None), ("% Costo Mercadería", "double", "0%")],
    "Meses de Vida": [("Mes de Vida", "int64", "0")],
}


def strip_measures(text, names):
    """Quita los bloques 'measure' (con su descripción ///) cuyos nombres están en 'names'."""
    targets = {q(n) for n in names}
    lines, out, i = text.split("\n"), [], 0
    while i < len(lines):
        start = i
        while lines[i].startswith("\t///") and i + 1 < len(lines):
            i += 1
        m = re.match(r"\tmeasure ('(?:[^']|'')+'|[^\s=]+)", lines[i])
        if m and m.group(1) in targets:
            i += 1
            while i < len(lines) and (lines[i].startswith("\t\t") or not lines[i].strip()):
                i += 1
            continue
        out.extend(lines[start:i + 1])
        i += 1
    return "\n".join(out)


def write_param_columns():
    """Las tablas calculadas no traen formato: se declaran sus columnas explícitamente."""
    for table, cols in PARAM_COLUMNS.items():
        path = MODEL_TABLES / f"{table}.tmdl"
        text = re.sub(r"(?m)^\tcolumn [^\n]*\n(?:\t\t[^\n]*\n|\r?\n)*", "", path.read_text(encoding="utf-8"))
        block = ""
        for name, dtype, fmt in cols:
            block += f"\tcolumn {q(name)}\n\t\tdataType: {dtype}\n"
            if fmt:
                block += f"\t\tformatString: {fmt}\n"
            block += f"\t\tsummarizeBy: none\n\t\tisNameInferred\n\t\tsourceColumn: [{name}]\n\n"
        path.write_text(text.replace("\tpartition ", block + "\tpartition ", 1), encoding="utf-8")


def main():
    ensure_power_bi_closed()
    generated = [m for kpi, kind, up in KPIS for m in delta_measures(kpi, kind, up)] + OTHER
    text = strip_measures(MEDIDAS.read_text(encoding="utf-8"), [n for n, _ in generated] + LEGACY)
    marker = "\tcolumn Oculta"
    if marker not in text:
        raise SystemExit("No se encontró la columna 'Oculta' en Medidas.tmdl (punto de inserción).")
    blocks = "\n\n".join(block for _, block in generated) + "\n\n"
    MEDIDAS.write_text(text.replace(marker, blocks + marker, 1), encoding="utf-8")
    write_param_columns()
    print(f"medidas generadas: {len(generated)}")


if __name__ == "__main__":
    main()

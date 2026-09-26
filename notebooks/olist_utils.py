"""Utilidades compartidas por los notebooks del proyecto Olist.

Centraliza tres cosas que antes estaban copiadas en cada notebook:
- dónde están los datos (repo local o Google Drive en Colab),
- cómo pasar del archivo plano a cada granularidad (pedido, ítem, pago, cliente),
- el estilo de los gráficos (misma paleta que el dashboard de Power BI).
"""
from pathlib import Path

import matplotlib as mpl
import matplotlib.pyplot as plt
import matplotlib.ticker as mtick
import pandas as pd

# --------------------------------------------------------------------------- rutas
RAIZ = Path(__file__).resolve().parent.parent
DATA = RAIZ / "data"
RAW = DATA / "raw"
DRIVE = Path("/content/drive/MyDrive/Proyecto Análisis Avanzado de Datos y Sentimientos en E-Commerce")


def ruta(nombre: str, carpeta: Path = DATA) -> Path:
    """Devuelve la ruta de un archivo de datos: primero el repo, después Drive (Colab)."""
    for base in (carpeta, DRIVE):
        if (base / nombre).exists():
            return base / nombre
    raise FileNotFoundError(
        f"No encuentro {nombre}. Descargá el dataset de Kaggle "
        f"(https://www.kaggle.com/datasets/olistbr/brazilian-ecommerce) en {carpeta}."
    )


# ------------------------------------------------------------------- granularidades
FECHAS = [
    "order_purchase_timestamp", "order_approved_at", "order_delivered_carrier_date",
    "order_delivered_customer_date", "order_estimated_delivery_date", "shipping_limit_date",
]

# Columnas que describen al pedido completo (se repiten en cada fila del archivo plano)
COLS_PEDIDO = [
    "order_id", "order_status", "customer_unique_id", "customer_state", "customer_full_state",
    "customer_region", "order_purchase_timestamp", "order_approved_at",
    "order_delivered_carrier_date", "order_delivered_customer_date",
    "order_estimated_delivery_date", "review_score", "processing_time", "approval_time",
    "prep_time", "delivery_delay", "on_time", "late_delivery", "hour", "day_of_week",
    "month_year", "max_order_item_id", "max_payment_sequential", "most_frequent_payment_type",
    "precio_ticket", "rango_ticket", "num_pedidos", "frecuencia_compra",
]
COLS_ITEM = [
    "order_id", "order_item_id", "product_id", "seller_id", "seller_names", "seller_state",
    "seller_region", "shipping_limit_date", "shipping_late_days", "price", "freight_value",
    "product_category_name_es", "macro_category", "order_purchase_timestamp", "customer_state",
    "customer_region", "month_year",
]
COLS_PAGO = ["order_id", "payment_sequential", "payment_type", "payment_installments", "payment_value"]


def cargar_eda() -> pd.DataFrame:
    """Lee df_EDA.csv: una fila por combinación pedido × ítem × pago."""
    return pd.read_csv(ruta("df_EDA.csv"), parse_dates=FECHAS)


def nivel_pedido(df: pd.DataFrame) -> pd.DataFrame:
    """Una fila por pedido. Usar para ventas, ticket, entregas y reseñas."""
    return df.drop_duplicates("order_id")[COLS_PEDIDO].reset_index(drop=True)


def nivel_item(df: pd.DataFrame) -> pd.DataFrame:
    """Una fila por ítem vendido. Usar para categorías, productos y vendedores."""
    return df.drop_duplicates(["order_id", "order_item_id"])[COLS_ITEM].reset_index(drop=True)


def nivel_pago(df: pd.DataFrame) -> pd.DataFrame:
    """Una fila por pago. Usar para medios de pago y cuotas."""
    return df.drop_duplicates(["order_id", "payment_sequential"])[COLS_PAGO].reset_index(drop=True)


def nivel_cliente(pedidos: pd.DataFrame) -> pd.DataFrame:
    """Una fila por cliente (customer_unique_id) a partir de la tabla de pedidos."""
    return (
        pedidos.groupby("customer_unique_id")
        .agg(
            pedidos=("order_id", "nunique"),
            gasto=("precio_ticket", "sum"),
            primera_compra=("order_purchase_timestamp", "min"),
            ultima_compra=("order_purchase_timestamp", "max"),
            estado=("customer_state", "first"),
            region=("customer_region", "first"),
        )
        .reset_index()
    )


# --------------------------------------------------------------------------- estilo
AZUL, NARANJA, VERDE, OCRE, VIOLETA = "#3B78F0", "#D95926", "#199E70", "#C98500", "#9085E9"
PALETA = [AZUL, NARANJA, VERDE, OCRE, VIOLETA]
GRIS = "#9AA3B2"
TINTA = "#1F2937"
TINTA_2 = "#5B6475"
BIEN, ALERTA, MAL = "#0CA30C", "#FAB219", "#D03B3B"


def estilo() -> None:
    """Estilo común: fondo claro, ejes discretos, paleta del dashboard."""
    mpl.rcParams.update({
        "figure.figsize": (10, 4.2),
        "figure.dpi": 110,
        "figure.facecolor": "white",
        "axes.facecolor": "white",
        "axes.edgecolor": "#D5D9E0",
        "axes.labelcolor": TINTA_2,
        "axes.titlesize": 13,
        "axes.titleweight": "bold",
        "axes.titlecolor": TINTA,
        "axes.titlelocation": "left",
        "axes.titlepad": 12,
        "axes.spines.top": False,
        "axes.spines.right": False,
        "axes.grid": True,
        "axes.grid.axis": "y",
        "axes.axisbelow": True,
        "grid.color": "#EDEFF3",
        "grid.linewidth": 0.8,
        "axes.prop_cycle": mpl.cycler(color=PALETA),
        "xtick.color": TINTA_2,
        "ytick.color": TINTA_2,
        "legend.frameon": False,
        "font.size": 10,
        "text.parse_math": False,  # "R$" no es LaTeX
    })
    pd.set_option("display.max_columns", 40)
    pd.set_option("display.float_format", "{:,.2f}".format)


def fmt_miles(ax, eje: str = "y", prefijo: str = "") -> None:
    """Formatea un eje en miles/millones: 1.2M, 350k."""
    def _f(x, _):
        if abs(x) >= 1e6:
            return f"{prefijo}{x / 1e6:.1f}M"
        if abs(x) >= 1e3:
            return f"{prefijo}{x / 1e3:.0f}k"
        return f"{prefijo}{x:.0f}"
    (ax.yaxis if eje == "y" else ax.xaxis).set_major_formatter(mtick.FuncFormatter(_f))


def fmt_pct(ax, eje: str = "y", decimales: int = 0) -> None:
    """Formatea un eje con valores 0–1 como porcentaje."""
    (ax.yaxis if eje == "y" else ax.xaxis).set_major_formatter(mtick.PercentFormatter(1, decimales))


def barras_h(serie: pd.Series, titulo: str, ax=None, color: str = AZUL, fmt: str = "{:,.0f}",
             resaltar: int = 0, xlabel: str = ""):
    """Barras horizontales ordenadas con el valor escrito al final de cada barra.

    `resaltar` pinta las primeras n barras con `color` y el resto en gris.
    """
    serie = serie.sort_values()
    if ax is None:
        _, ax = plt.subplots(figsize=(10, 0.32 * len(serie) + 1.2))
    colores = [color] * len(serie)
    if resaltar:
        colores = [GRIS] * (len(serie) - resaltar) + [color] * resaltar
    ax.barh(serie.index.astype(str), serie.values, color=colores, height=0.7)
    ax.grid(axis="y", visible=False)
    ax.grid(axis="x", visible=True)
    ax.set_title(titulo)
    ax.set_xlabel(xlabel)
    ancho = serie.abs().max()
    for i, v in enumerate(serie.values):
        ax.text(v + ancho * 0.01, i, fmt.format(v), va="center", fontsize=9, color=TINTA)
    ax.set_xlim(0, ancho * 1.15)
    return ax


def tabla(df: pd.DataFrame, formatos) -> pd.DataFrame:
    """Copia de `df` con los números formateados como texto, para mostrar.

    `formatos` es un formato único ("{:.1%}") o un dict {columna: formato}.
    """
    salida = df.copy()
    for col in salida.columns:
        fmt = formatos if isinstance(formatos, str) else formatos.get(col)
        if fmt:
            salida[col] = salida[col].map(lambda v: fmt.format(v) if pd.notna(v) else "")
    return salida


def pie_de_fuente(fig, texto: str = "Fuente: Olist (Kaggle), pedidos con ciclo completo 2016-10 a 2018-08.") -> None:
    fig.text(0.01, -0.02, texto, fontsize=8, color=TINTA_2, ha="left")

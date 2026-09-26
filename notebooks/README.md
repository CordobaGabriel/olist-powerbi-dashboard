# Notebooks

Análisis en Python que alimenta el dashboard. Se leen en orden:

| Notebook | Pregunta | Resultado |
|---|---|---|
| [01 · Preparación de datos](01_preparacion_datos.ipynb) | ¿Qué datos entran y cómo se integran? | `data/df_EDA.csv`, la tabla que usan el EDA y Power BI |
| [02 · Análisis exploratorio](02_analisis_exploratorio.ipynb) | ¿Cómo evolucionan las ventas, dónde fallan las entregas y quién vuelve a comprar? | 8 hallazgos que definen las páginas del dashboard |
| [03 · Satisfacción y sentimiento](03_satisfaccion_y_sentimiento.ipynb) | ¿Qué explica una reseña de 1–2 estrellas? | Modelo con AUC 0,75 en meses no vistos y 4 recomendaciones |

**Principios que siguen los tres**

- **Cada métrica en su granularidad.** El archivo plano repite filas (ítem × pago); sumarlo directo infla las ventas un 28%. [`olist_utils.py`](olist_utils.py) tiene una función por nivel: `nivel_pedido`, `nivel_item`, `nivel_pago` y `nivel_cliente`.
- **Gráficos estáticos.** Se ven en GitHub sin ejecutar nada, usan la misma paleta que el dashboard y ninguno tiene doble eje.
- **Rutas portables.** Los datos se buscan en `data/` del repo y, si no están, en la carpeta del proyecto en Google Drive (Colab).

## Cómo ejecutarlos

```bash
pip install -r notebooks/requirements.txt
```

1. Descargá el [dataset de Olist en Kaggle](https://www.kaggle.com/datasets/olistbr/brazilian-ecommerce) y descomprimilo en `data/raw/`.
2. Ejecutá `01_preparacion_datos.ipynb`: genera `data/df_EDA.csv`.
3. Ejecutá `02` y `03` en cualquier orden.

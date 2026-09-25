# Olist E-commerce · Executive Dashboard in Power BI

An executive dashboard for **Olist**, the Brazilian e-commerce marketplace, built to answer three questions a leadership team asks every month: *are we on track?*, *why?* and *where do we act first?*

The dashboard is in Spanish. It is a Power BI Project (PBIP): the semantic model (TMDL) and the report (PBIR) are plain text, versioned here and generated/validated with Python.

![Executive summary](docs/img/resumen.png)

## Key findings (Jan–Aug 2018)

| | |
|---|---|
| **Growth** | Sales R$ 8.4M, **+146.5%** vs. the same period of 2017 and **112%** of the target so far. |
| **Year-end risk** | At the current run-rate the year closes at **R$ 12.6M, 83% of the R$ 15.2M annual target**. |
| **Logistics** | Late deliveries **worsened 4.3 pp** (7.8%). **75%** of them happen in transit, not in seller dispatch (9.0 vs. 2.5 days). |
| **Satisfaction** | Late orders score **2.24 / 5** vs. **4.30** for on-time ones. Avoiding half of the late deliveries would lift the average from 4.14 to 4.22. |
| **Concentration** | **16 of 63 categories** generate 80% of the contribution margin. |
| **Retention** | Only 2.1% of customers buy again, and monthly cohort retention stays below 1%. |

> Margin figures use **editable cost assumptions** (cost of goods by category, 3% payment fee), since Olist does not publish costs. Targets assume +120% over the previous year. Both are flagged as assumptions in the report.

## Pages

| Page | What it answers |
|---|---|
| **Resumen** | KPIs vs. prior year and target, monthly sales vs. target, target attainment by category, year-end projection. |
| **Rentabilidad** | Contribution margin by category, Pareto/ABC and margin concentration. |
| **Operación** | Root cause of late deliveries (seller dispatch vs. carrier) and a ranking of sellers to review. |
| **Clientes** | Retention by first-purchase cohort, purchase frequency and ticket ranges. |
| **Planificación** | Actual vs. projection vs. target, plus what-if scenarios (growth target, fewer late deliveries). |

<p>
  <img src="docs/img/rentabilidad.png" width="49%">
  <img src="docs/img/operacion.png" width="49%">
  <img src="docs/img/clientes.png" width="49%">
  <img src="docs/img/planificacion.png" width="49%">
</p>

## Data model

A star schema built in Power Query from a single flat file, replacing the original one-table model, which inflated sales by 28% because payments were repeated once per order item.

- **Facts:** `Items` (109,796 order items) and `Pagos` (100,396 payments), both related to `Pedidos` (96,124 orders).
- **Dimensions:** `Clientes`, `Productos`, `Vendedores` and a marked `Calendario` date table.
- **Measures:** 120+ DAX measures in folders: sales, orders, customers, logistics, reviews, profitability, prior-year comparisons, targets and projection, scenarios, and SVG visuals rendered inside tables.
- **Design choices:** a single bidirectional relationship (`Items`↔`Pedidos`) so product filters reach order-level KPIs; prior-year comparisons capped at the last date with data; a precomputed `Recompras` table so the cohort matrix renders in ~0.2 s instead of ~8 s.

## Report design

- One dark theme with a categorical palette **validated for color-vision deficiency** on the dark surface.
- No dual-axis charts. Target and projection lines are dashed. Variance is shown with ▲/▼ and a label, never with color alone.
- Page backgrounds are designed in HTML/CSS and rendered to PNG. The native Power BI visuals are placed on top using the same coordinates from [`design/layout.json`](design/layout.json).

## Repository structure

```
Olist_Dashboard.pbip              ← open this in Power BI Desktop
Olist_Dashboard.SemanticModel/    ← model (TMDL)
Olist_Dashboard.Report/           ← report (PBIR)
powerquery/                       ← Power Query (M) scripts for each table
design/
  layout.json                     ← palette and geometry of every page (single source of truth)
  build.py                        ← regenerates everything, in order
  build_model_extras.py           ← pattern-based DAX measures (prior year, variance, SVG)
  build_backgrounds.py            ← HTML page backgrounds → PNG (headless Edge)
  build_report.py                 ← PBIR pages and visuals
  validate.py                     ← checks that every field used by a visual exists in the model
```

## How to open it

1. Download the [Olist dataset from Kaggle](https://www.kaggle.com/datasets/olistbr/brazilian-ecommerce). The model reads `df_EDA.csv`, the consolidated file produced by the EDA notebooks of this project.
2. Put the file in `data/df_EDA.csv`, or change the `RutaCSV` parameter in Power Query.
3. Open `Olist_Dashboard.pbip` in Power BI Desktop and refresh.

To regenerate the model extras, backgrounds and pages after editing `design/layout.json` (Windows, Python 3.10+, Microsoft Edge, with Power BI Desktop closed):

```
python design/build.py
```

## Tools

Power BI Desktop (PBIP/TMDL/PBIR) · DAX · Power Query (M) · Python · HTML/CSS

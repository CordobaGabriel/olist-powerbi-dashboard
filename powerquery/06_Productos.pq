// Productos: una fila por producto (32.210) con su categoría y macro categoría.
let
    Origen = Olist_Base,
    Columnas = Table.SelectColumns(
        Origen,
        {"product_id", "product_category_name_es", "macro_category", "freq_score_categoria"}
    ),
    Unicos = Table.Distinct(Columnas, {"product_id"})
in
    Unicos

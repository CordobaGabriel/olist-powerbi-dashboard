// Vendedores: una fila por seller (2.970).
let
    Origen = Olist_Base,
    Columnas = Table.SelectColumns(
        Origen,
        {"seller_id", "seller_names", "seller_state", "seller_full_state", "seller_region"}
    ),
    Unicos = Table.Distinct(Columnas, {"seller_id"})
in
    Unicos

// Clientes: una fila por cliente (93.011). Si un cliente cambió de estado, se toma el de su último pedido.
let
    Origen = Olist_Base,
    Columnas = Table.SelectColumns(
        Origen,
        {
            "customer_unique_id", "order_purchase_timestamp", "customer_state", "customer_full_state",
            "customer_region", "num_pedidos", "frecuencia_compra", "freq_score"
        }
    ),
    Ordenado = Table.Buffer(Table.Sort(Columnas, {{"order_purchase_timestamp", Order.Descending}})),
    Unicos = Table.Distinct(Ordenado, {"customer_unique_id"}),
    SinFecha = Table.RemoveColumns(Unicos, {"order_purchase_timestamp"})
in
    SinFecha

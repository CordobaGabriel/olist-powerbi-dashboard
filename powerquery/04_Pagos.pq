// Pagos: una fila por pago de pedido (100.396). Método de pago, cuotas y monto.
let
    Origen = Olist_Base,
    Columnas = Table.SelectColumns(
        Origen,
        {"order_id", "payment_sequential", "payment_type", "payment_installments", "payment_value"}
    ),
    Unicos = Table.Distinct(Columnas, {"order_id", "payment_sequential"})
in
    Unicos

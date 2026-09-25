// Pedidos: una fila por pedido (96.124). Fechas, estado, reseña y métricas de entrega.
let
    Origen = Olist_Base,
    Columnas = Table.SelectColumns(
        Origen,
        {
            "order_id", "customer_unique_id", "order_status",
            "order_purchase_timestamp", "order_approved_at", "order_delivered_carrier_date",
            "order_delivered_customer_date", "order_estimated_delivery_date",
            "review_score", "processing_time", "approval_time", "prep_time",
            "shipping_late_days", "delivery_delay", "on_time", "late_delivery", "late_delivery_label",
            "hour", "day_of_week", "max_order_item_id", "max_payment_sequential",
            "most_frequent_payment_type", "precio_ticket", "beneficio_ticket", "rango_ticket",
            "VM_score", "Total_score", "dias_entre_compras", "frecuencia_temporal"
        }
    ),
    Unicos = Table.Distinct(Columnas, {"order_id"}),
    FechaCompra = Table.AddColumn(Unicos, "fecha_compra", each DateTime.Date([order_purchase_timestamp]), type date),
    // 9999 = "sin compra previa" en el dataset original: se deja como nulo para no distorsionar promedios
    SinCentinela = Table.ReplaceValue(FechaCompra, 9999, null, Replacer.ReplaceValue, {"dias_entre_compras"})
in
    SinCentinela

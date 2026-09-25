// Consulta base (NO se carga al modelo): lee el CSV y define los tipos con cultura en-US
// para que los decimales con punto se interpreten bien sin reemplazos manuales.
let
    Origen = Csv.Document(File.Contents(RutaCSV), [Delimiter = ",", Encoding = 65001, QuoteStyle = QuoteStyle.Csv]),
    Encabezados = Table.PromoteHeaders(Origen, [PromoteAllScalars = true]),
    Tipos = Table.TransformColumnTypes(
        Encabezados,
        {
            {"order_purchase_timestamp", type datetime},
            {"order_approved_at", type datetime},
            {"order_delivered_carrier_date", type datetime},
            {"order_delivered_customer_date", type datetime},
            {"order_estimated_delivery_date", type date},
            {"shipping_limit_date", type datetime},
            {"order_item_id", Int64.Type},
            {"price", Currency.Type},
            {"freight_value", Currency.Type},
            {"payment_sequential", Int64.Type},
            {"payment_installments", Int64.Type},
            {"payment_value", Currency.Type},
            {"review_score", Int64.Type},
            {"hour", Int64.Type},
            {"processing_time", Int64.Type},
            {"approval_time", Int64.Type},
            {"prep_time", Int64.Type},
            {"shipping_late_days", Int64.Type},
            {"delivery_delay", Int64.Type},
            {"on_time", type logical},
            {"late_delivery", type logical},
            {"max_order_item_id", Int64.Type},
            {"max_payment_sequential", Int64.Type},
            {"precio_ticket", Currency.Type},
            {"beneficio_ticket", Currency.Type},
            {"num_pedidos", Int64.Type},
            {"freq_score", Int64.Type},
            {"VM_score", Int64.Type},
            {"Total_score", Int64.Type},
            {"dias_entre_compras", type number},
            {"freq_score_categoria", Int64.Type},
            {"score_valor_producto", Int64.Type},
            {"total_score_categoria", Int64.Type}
        },
        "en-US"
    )
in
    Tipos

// Items: una fila por ítem de pedido (109.796). Fuente de ventas (precio + flete) por producto/seller.
let
    Origen = Olist_Base,
    Columnas = Table.SelectColumns(
        Origen,
        {
            "order_id", "order_item_id", "product_id", "seller_id", "shipping_limit_date",
            "price", "freight_value", "rango_precio_producto", "score_valor_producto", "total_score_categoria"
        }
    ),
    Unicos = Table.Distinct(Columnas, {"order_id", "order_item_id"})
in
    Unicos

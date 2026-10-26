-- Pending orders and packages by carrier, with how many of them are critical.
SELECT
    c.carrier_name,
    COUNT(o.order_id) AS pending_orders,
    CAST(COALESCE(SUM(o.packages), 0) AS INTEGER) AS pending_packages,
    COUNT(o.order_id) FILTER (WHERE o.is_critical) AS critical_orders
FROM dim_carrier AS c
LEFT JOIN fact_pickup_order AS o
       ON o.carrier_id = c.carrier_id
      AND o.status IN ('EN GESTION', 'RETIRADO')
GROUP BY c.carrier_name
ORDER BY pending_packages DESC;

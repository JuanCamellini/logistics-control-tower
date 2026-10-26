-- Age of pending orders by delay range, split by status.
SELECT
    delay_bucket,
    COUNT(*) FILTER (WHERE status = 'EN GESTION') AS in_progress_orders,
    COUNT(*) FILTER (WHERE status = 'RETIRADO') AS picked_up_orders,
    COUNT(*) AS pending_orders
FROM fact_pickup_order
WHERE status IN ('EN GESTION', 'RETIRADO')
GROUP BY delay_bucket
ORDER BY CASE delay_bucket
    WHEN '0 - 7 días' THEN 1
    WHEN '8 - 15 días' THEN 2
    WHEN '16 - 30 días' THEN 3
    WHEN '31 - 60 días' THEN 4
    ELSE 5
END;

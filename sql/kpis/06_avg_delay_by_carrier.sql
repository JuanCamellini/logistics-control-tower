-- Average delay days of pending orders, by carrier and status.
SELECT
    c.carrier_name,
    o.status,
    COUNT(*) AS orders,
    ROUND(AVG(o.delay_days), 1) AS avg_delay_days
FROM fact_pickup_order AS o
JOIN dim_carrier AS c ON c.carrier_id = o.carrier_id
WHERE o.status IN ('EN GESTION', 'RETIRADO')
GROUP BY c.carrier_name, o.status
ORDER BY c.carrier_name, o.status;

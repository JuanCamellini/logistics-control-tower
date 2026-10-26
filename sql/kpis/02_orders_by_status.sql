-- Number of orders in each status.
SELECT
    status,
    COUNT(*) AS orders,
    CAST(SUM(packages) AS INTEGER) AS packages
FROM fact_pickup_order
GROUP BY status
ORDER BY orders DESC;

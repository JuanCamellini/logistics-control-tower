-- Pending packages by customer province.
SELECT
    cu.province,
    COUNT(*) AS pending_orders,
    CAST(SUM(o.packages) AS INTEGER) AS pending_packages
FROM fact_pickup_order AS o
JOIN dim_customer AS cu ON cu.customer_id = o.customer_id
WHERE o.status IN ('EN GESTION', 'RETIRADO')
GROUP BY cu.province
ORDER BY pending_packages DESC;

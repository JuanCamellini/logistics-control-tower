-- The numbers on the dashboard cards, in one row.
-- Pending = EN GESTION or RETIRADO. Critical orders are pending orders past their SLA.
-- Cycle time: calendar days from document to depot, for orders already at the depot.
SELECT
    COUNT(*) AS total_orders,
    CAST(SUM(packages) AS INTEGER) AS total_packages,
    COUNT(*) FILTER (WHERE status = 'EN GESTION') AS in_progress_orders,
    CAST(COALESCE(SUM(packages) FILTER (WHERE status = 'EN GESTION'), 0) AS INTEGER) AS in_progress_packages,
    COUNT(*) FILTER (WHERE status = 'RETIRADO') AS picked_up_orders,
    CAST(COALESCE(SUM(packages) FILTER (WHERE status = 'RETIRADO'), 0) AS INTEGER) AS picked_up_packages,
    COUNT(*) FILTER (WHERE is_critical) AS critical_orders,
    CAST(COALESCE(SUM(packages) FILTER (WHERE is_critical), 0) AS INTEGER) AS critical_packages,
    ROUND(COUNT(*) FILTER (WHERE is_critical) * 1.0
          / NULLIF(COUNT(*) FILTER (WHERE status IN ('EN GESTION', 'RETIRADO')), 0), 4) AS critical_rate,
    ROUND(COUNT(*) FILTER (WHERE status = 'DEPURADA') * 1.0 / COUNT(*), 4) AS purged_rate,
    ROUND(AVG(delay_days) FILTER (WHERE status = 'EN PUNTO DE CONTROL'), 1) AS avg_cycle_days
FROM fact_pickup_order;

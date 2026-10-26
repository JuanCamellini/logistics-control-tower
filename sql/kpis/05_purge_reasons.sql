-- Why orders were purged (DEPURADA), from the incident category derived from the notes.
SELECT
    incident_category,
    COUNT(*) AS orders
FROM fact_pickup_order
WHERE status = 'DEPURADA'
GROUP BY incident_category
ORDER BY orders DESC, incident_category;

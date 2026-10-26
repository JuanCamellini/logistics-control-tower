-- Star schema for pick-up order traceability.
-- Standard SQL: runs on DuckDB and PostgreSQL.

CREATE TABLE dim_carrier (
    carrier_id       VARCHAR(10) PRIMARY KEY,
    carrier_name     VARCHAR(60) NOT NULL,
    pickup_sla_days  INTEGER NOT NULL,   -- business days from sent date to pick-up
    depot_sla_days   INTEGER NOT NULL    -- business days from pick-up to arrival at the depot
);

CREATE TABLE dim_customer (
    customer_id    INTEGER PRIMARY KEY,
    customer_name  VARCHAR(100) NOT NULL,
    street         VARCHAR(100),
    locality       VARCHAR(60),
    province       VARCHAR(40),
    route_code     VARCHAR(60),
    route          VARCHAR(20)          -- CABA, GBA, Interior, Costa Atlántica
);

CREATE TABLE dim_date (
    date_key         DATE PRIMARY KEY,
    year             INTEGER NOT NULL,
    month            INTEGER NOT NULL,
    month_name       VARCHAR(12) NOT NULL,
    is_business_day  BOOLEAN NOT NULL
);

CREATE TABLE meta_snapshot (
    as_of_date  DATE NOT NULL           -- the day the master was refreshed
);

-- One row per pick-up order.
CREATE TABLE fact_pickup_order (
    order_id                 BIGINT PRIMARY KEY,
    customer_id              INTEGER NOT NULL REFERENCES dim_customer (customer_id),
    carrier_id               VARCHAR(10) NOT NULL REFERENCES dim_carrier (carrier_id),
    document_date            DATE NOT NULL,
    sent_date                DATE NOT NULL,
    expected_pickup_date     DATE,
    pickup_date              DATE,
    expected_arrival_date    DATE,
    arrival_date             DATE,
    packages                 INTEGER NOT NULL,
    status                   VARCHAR(25) NOT NULL
        CHECK (status IN ('EN GESTION', 'RETIRADO', 'EN PUNTO DE CONTROL', 'DEPURADA', 'DEPURAR')),
    is_critical              BOOLEAN NOT NULL,
    alert_sent               BOOLEAN NOT NULL,
    delay_days               INTEGER,  -- calendar days from document to depot (or to the snapshot date)
    delay_bucket             VARCHAR(15),
    business_days_in_status  INTEGER,  -- only for EN GESTION and RETIRADO
    notes                    VARCHAR(200),
    incident_category        VARCHAR(60) NOT NULL,
    -- Each leg measured in business days, until the snapshot date if still open
    pickup_business_days     INTEGER,      -- sent -> pick-up
    pickup_sla_status        VARCHAR(15),  -- En plazo, Fuera de plazo, En curso
    depot_business_days      INTEGER,      -- pick-up -> depot
    depot_sla_status         VARCHAR(15)
);

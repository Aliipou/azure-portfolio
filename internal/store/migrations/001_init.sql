CREATE TABLE IF NOT EXISTS devices (
    id               TEXT PRIMARY KEY,
    tenant_id        TEXT NOT NULL,
    name             TEXT NOT NULL,
    serial_number    TEXT NOT NULL,
    device_type      TEXT NOT NULL CHECK (device_type IN ('pressure','temperature','electrical','flow')),
    location         TEXT NOT NULL,
    manufacturer     TEXT NOT NULL DEFAULT '',
    model            TEXT NOT NULL DEFAULT '',
    tolerance_pct    DOUBLE PRECISION NOT NULL DEFAULT 0.5,
    is_active        BOOLEAN NOT NULL DEFAULT TRUE,
    last_calibrated_at TIMESTAMPTZ,
    created_at       TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    UNIQUE(serial_number, tenant_id)
);

CREATE INDEX IF NOT EXISTS idx_devices_tenant ON devices(tenant_id);

CREATE TABLE IF NOT EXISTS calibration_records (
    id            TEXT PRIMARY KEY,
    device_id     TEXT NOT NULL REFERENCES devices(id) ON DELETE CASCADE,
    tenant_id     TEXT NOT NULL,
    operator_name TEXT NOT NULL,
    temperature_c DOUBLE PRECISION,
    humidity_pct  DOUBLE PRECISION,
    status        TEXT NOT NULL DEFAULT 'pending' CHECK (status IN ('pending','pass','fail','invalid')),
    overall_pass  BOOLEAN NOT NULL DEFAULT FALSE,
    pass_count    INT NOT NULL DEFAULT 0,
    fail_count    INT NOT NULL DEFAULT 0,
    measured_at   TIMESTAMPTZ NOT NULL,
    created_at    TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_cal_records_device ON calibration_records(device_id);
CREATE INDEX IF NOT EXISTS idx_cal_records_tenant ON calibration_records(tenant_id);

CREATE TABLE IF NOT EXISTS calibration_measurements (
    id                   TEXT PRIMARY KEY,
    record_id            TEXT NOT NULL REFERENCES calibration_records(id) ON DELETE CASCADE,
    measured_value       DOUBLE PRECISION NOT NULL,
    reference_value      DOUBLE PRECISION NOT NULL,
    unit                 TEXT NOT NULL,
    uncertainty          DOUBLE PRECISION NOT NULL DEFAULT 0,
    deviation_pct        DOUBLE PRECISION NOT NULL,
    expanded_uncertainty DOUBLE PRECISION NOT NULL,
    is_pass              BOOLEAN NOT NULL
);

CREATE INDEX IF NOT EXISTS idx_cal_meas_record ON calibration_measurements(record_id);

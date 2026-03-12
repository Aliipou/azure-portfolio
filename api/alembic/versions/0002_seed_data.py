"""Seed data — 10 devices and 100 calibration measurements for demo.

Revision ID: 0002
Revises: 0001
Create Date: 2024-03-01 00:01:00.000000
"""
from __future__ import annotations

import uuid
from datetime import datetime, timedelta, timezone

from alembic import op
import sqlalchemy as sa

revision = "0002"
down_revision = "0001"
branch_labels = None
depends_on = None


DEVICES = [
    {"id": "PG-001", "name": "Pressure Gauge Alpha", "device_type": "PRESSURE", "serial_number": "SN-PG-001", "manufacturer": "Beamex", "model": "MC6-T", "location": "Lab A"},
    {"id": "PG-002", "name": "Pressure Gauge Beta", "device_type": "PRESSURE", "serial_number": "SN-PG-002", "manufacturer": "Beamex", "model": "MC6-T", "location": "Lab A"},
    {"id": "TH-001", "name": "Thermometer Alpha", "device_type": "TEMPERATURE", "serial_number": "SN-TH-001", "manufacturer": "Beamex", "model": "TC Calibrator", "location": "Lab B"},
    {"id": "TH-002", "name": "Thermometer Beta", "device_type": "TEMPERATURE", "serial_number": "SN-TH-002", "manufacturer": "Fluke", "model": "1524", "location": "Lab B"},
    {"id": "EL-001", "name": "Electrical Meter Alpha", "device_type": "ELECTRICAL", "serial_number": "SN-EL-001", "manufacturer": "Beamex", "model": "CB9000", "location": "Lab C"},
    {"id": "EL-002", "name": "Electrical Meter Beta", "device_type": "ELECTRICAL", "serial_number": "SN-EL-002", "manufacturer": "Fluke", "model": "8588A", "location": "Lab C"},
    {"id": "FL-001", "name": "Flow Meter Alpha", "device_type": "FLOW", "serial_number": "SN-FL-001", "manufacturer": "Endress+Hauser", "model": "Promag P300", "location": "Lab D"},
    {"id": "FL-002", "name": "Flow Meter Beta", "device_type": "FLOW", "serial_number": "SN-FL-002", "manufacturer": "Krohne", "model": "OPTIFLUX", "location": "Lab D"},
    {"id": "PG-003", "name": "Pressure Gauge Gamma", "device_type": "PRESSURE", "serial_number": "SN-PG-003", "manufacturer": "Druck", "model": "DPI 620", "location": "Field"},
    {"id": "TH-003", "name": "Thermometer Gamma", "device_type": "TEMPERATURE", "serial_number": "SN-TH-003", "manufacturer": "Hart Scientific", "model": "1529", "location": "Field"},
]


def upgrade() -> None:
    connection = op.get_bind()
    now = datetime.now(timezone.utc)

    # Insert devices
    for device in DEVICES:
        connection.execute(
            sa.text("""
                INSERT INTO devices (id, name, device_type, serial_number, manufacturer, model, location, is_active, created_at, updated_at)
                VALUES (:id, :name, :device_type, :serial_number, :manufacturer, :model, :location, true, :now, :now)
                ON CONFLICT (id) DO NOTHING
            """),
            {**device, "now": now},
        )

    # Insert 10 measurements per device (100 total)
    base_configs = {
        "PRESSURE": {"ref": 100.0, "uncertainty": 0.15, "unit": "bar"},
        "TEMPERATURE": {"ref": 20.0, "uncertainty": 0.05, "unit": "°C"},
        "ELECTRICAL": {"ref": 10.0, "uncertainty": 0.01, "unit": "V"},
        "FLOW": {"ref": 50.0, "uncertainty": 0.5, "unit": "L/min"},
    }

    operators = ["op-alice", "op-bob", "op-carol"]

    for device in DEVICES:
        cfg = base_configs[device["device_type"]]
        for i in range(10):
            measured_at = now - timedelta(days=i * 3)
            # Make measurement 9 an anomaly (high z-score)
            deviation = 0.05 * i if i < 9 else cfg["uncertainty"] * 5
            measured_value = cfg["ref"] + deviation
            status = "ANOMALY" if i == 9 else "VALIDATED"
            m_id = str(uuid.uuid4())

            connection.execute(
                sa.text("""
                    INSERT INTO calibration_measurements
                    (id, device_id, measurement_type, measured_value, reference_value,
                     uncertainty, unit, operator_id, status, measured_at, created_at)
                    VALUES (:id, :device_id, :measurement_type, :measured_value, :reference_value,
                            :uncertainty, :unit, :operator_id, :status, :measured_at, :created_at)
                """),
                {
                    "id": m_id,
                    "device_id": device["id"],
                    "measurement_type": device["device_type"],
                    "measured_value": measured_value,
                    "reference_value": cfg["ref"],
                    "uncertainty": cfg["uncertainty"],
                    "unit": cfg["unit"],
                    "operator_id": operators[i % len(operators)],
                    "status": status,
                    "measured_at": measured_at,
                    "created_at": measured_at,
                },
            )

            # Insert analysis result
            z_score = abs(measured_value - cfg["ref"]) / cfg["uncertainty"]
            is_anomaly = z_score >= 3.0
            connection.execute(
                sa.text("""
                    INSERT INTO analysis_results
                    (id, measurement_id, z_score, is_anomaly, deviation_pct, confidence, model_version, details, analyzed_at)
                    VALUES (:id, :measurement_id, :z_score, :is_anomaly, :deviation_pct, :confidence, :model_version, :details, :analyzed_at)
                """),
                {
                    "id": str(uuid.uuid4()),
                    "measurement_id": m_id,
                    "z_score": z_score,
                    "is_anomaly": is_anomaly,
                    "deviation_pct": abs(measured_value - cfg["ref"]) / cfg["ref"] * 100,
                    "confidence": 0.95,
                    "model_version": "1.0.0",
                    "details": '{"threshold": 3.0}',
                    "analyzed_at": measured_at + timedelta(seconds=5),
                },
            )


def downgrade() -> None:
    connection = op.get_bind()
    connection.execute(sa.text("DELETE FROM analysis_results"))
    connection.execute(sa.text("DELETE FROM calibration_measurements"))
    for device in DEVICES:
        connection.execute(
            sa.text("DELETE FROM devices WHERE id = :id"),
            {"id": device["id"]},
        )

"""Initial schema — devices, measurements, analysis results, audit log.

Revision ID: 0001
Revises:
Create Date: 2024-03-01 00:00:00.000000
"""
from __future__ import annotations

from datetime import datetime, timezone

import sqlalchemy as sa
from alembic import op

revision = "0001"
down_revision = None
branch_labels = None
depends_on = None


def upgrade() -> None:
    # --- devices ---
    op.create_table(
        "devices",
        sa.Column("id", sa.String(64), primary_key=True),
        sa.Column("name", sa.String(255), nullable=False),
        sa.Column("device_type", sa.String(32), nullable=False),
        sa.Column("serial_number", sa.String(128), nullable=False, unique=True),
        sa.Column("manufacturer", sa.String(128), nullable=True),
        sa.Column("model", sa.String(128), nullable=True),
        sa.Column("location", sa.String(255), nullable=True),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default="true"),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("NOW()"),
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("NOW()"),
            onupdate=sa.text("NOW()"),
        ),
    )

    # --- calibration_measurements ---
    op.create_table(
        "calibration_measurements",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("device_id", sa.String(64), sa.ForeignKey("devices.id", ondelete="RESTRICT"), nullable=False),
        sa.Column("measurement_type", sa.String(32), nullable=False),
        sa.Column("measured_value", sa.Float(), nullable=False),
        sa.Column("reference_value", sa.Float(), nullable=False),
        sa.Column("uncertainty", sa.Float(), nullable=False),
        sa.Column("unit", sa.String(32), nullable=False),
        sa.Column("temperature_ambient", sa.Float(), nullable=True),
        sa.Column("operator_id", sa.String(128), nullable=False),
        sa.Column("status", sa.String(32), nullable=False, server_default="RECEIVED"),
        sa.Column(
            "measured_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("NOW()"),
        ),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("NOW()"),
        ),
    )
    op.create_index("ix_measurements_device_id", "calibration_measurements", ["device_id"])
    op.create_index("ix_measurements_status", "calibration_measurements", ["status"])
    op.create_index("ix_measurements_measured_at", "calibration_measurements", ["measured_at"])

    # --- analysis_results ---
    op.create_table(
        "analysis_results",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column(
            "measurement_id",
            sa.String(36),
            sa.ForeignKey("calibration_measurements.id", ondelete="CASCADE"),
            nullable=False,
            unique=True,
        ),
        sa.Column("z_score", sa.Float(), nullable=False),
        sa.Column("is_anomaly", sa.Boolean(), nullable=False),
        sa.Column("deviation_pct", sa.Float(), nullable=False),
        sa.Column("confidence", sa.Float(), nullable=False),
        sa.Column("model_version", sa.String(32), nullable=False),
        sa.Column("details", sa.JSON(), nullable=True),
        sa.Column(
            "analyzed_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("NOW()"),
        ),
    )
    op.create_index("ix_analysis_measurement_id", "analysis_results", ["measurement_id"])
    op.create_index("ix_analysis_is_anomaly", "analysis_results", ["is_anomaly"])

    # --- audit_logs ---
    op.create_table(
        "audit_logs",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("user_id", sa.String(128), nullable=False),
        sa.Column("user_email", sa.String(255), nullable=True),
        sa.Column("action", sa.String(64), nullable=False),
        sa.Column("resource_type", sa.String(64), nullable=False),
        sa.Column("resource_id", sa.String(128), nullable=True),
        sa.Column("details", sa.JSON(), nullable=True),
        sa.Column("ip_address", sa.String(45), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("NOW()"),
        ),
    )
    op.create_index("ix_audit_user_id", "audit_logs", ["user_id"])
    op.create_index("ix_audit_created_at", "audit_logs", ["created_at"])


def downgrade() -> None:
    op.drop_table("audit_logs")
    op.drop_table("analysis_results")
    op.drop_table("calibration_measurements")
    op.drop_table("devices")

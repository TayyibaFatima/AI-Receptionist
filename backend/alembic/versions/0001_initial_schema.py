"""Initial schema (creates tables only; never drops existing data).

Revision ID: 0001
Revises:
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision = "0001"
down_revision = None
branch_labels = None
depends_on = None

NOW = sa.text("now()")


def upgrade() -> None:
    op.create_table(
        "clinic_info",
        sa.Column("id", sa.Integer, primary_key=True),
        sa.Column("clinic_name", sa.String(150), nullable=False),
        sa.Column("address", sa.Text),
        sa.Column("phone", sa.String(50)),
        sa.Column("email", sa.String(150)),
        sa.Column("opening_hours", sa.Text),
        sa.Column("general_info", sa.Text),
        sa.Column("currency", sa.String(10), nullable=False, server_default="PKR"),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=NOW),
    )
    op.create_table(
        "services",
        sa.Column("id", sa.Integer, primary_key=True),
        sa.Column("name", sa.String(150), nullable=False, unique=True),
        sa.Column("category", sa.String(30), nullable=False),
        sa.Column("description", sa.Text),
        sa.Column("price", sa.Numeric(10, 2)),
        sa.Column("duration_minutes", sa.Integer),
        sa.Column("is_active", sa.Boolean, nullable=False, server_default=sa.true()),
        sa.CheckConstraint("category IN ('aesthetic_treatment','general_consultation')", name="ck_services_category"),
        sa.CheckConstraint("price IS NULL OR price >= 0", name="ck_services_price"),
        sa.CheckConstraint("duration_minutes IS NULL OR duration_minutes > 0", name="ck_services_duration"),
    )
    op.create_table(
        "doctors",
        sa.Column("id", sa.Integer, primary_key=True),
        sa.Column("full_name", sa.String(150), nullable=False),
        sa.Column("specialization", sa.String(100), nullable=False),
        sa.Column("profile_description", sa.Text),
        sa.Column("consultation_fee", sa.Numeric(10, 2)),
        sa.Column("is_active", sa.Boolean, nullable=False, server_default=sa.true()),
        sa.CheckConstraint("consultation_fee IS NULL OR consultation_fee >= 0", name="ck_doctors_fee"),
    )
    op.create_table(
        "doctor_services",
        sa.Column("doctor_id", sa.Integer, sa.ForeignKey("doctors.id", ondelete="CASCADE"), primary_key=True),
        sa.Column("service_id", sa.Integer, sa.ForeignKey("services.id", ondelete="CASCADE"), primary_key=True),
    )
    op.create_table(
        "doctor_schedules",
        sa.Column("id", sa.Integer, primary_key=True),
        sa.Column("doctor_id", sa.Integer, sa.ForeignKey("doctors.id", ondelete="CASCADE"), nullable=False),
        sa.Column("day_of_week", sa.SmallInteger, nullable=False),
        sa.Column("start_time", sa.Time, nullable=False),
        sa.Column("end_time", sa.Time, nullable=False),
        sa.Column("slot_minutes", sa.Integer, nullable=False, server_default="30"),
        sa.Column("is_active", sa.Boolean, nullable=False, server_default=sa.true()),
        sa.UniqueConstraint("doctor_id", "day_of_week", "start_time", name="uq_schedule_doctor_day_start"),
        sa.CheckConstraint("day_of_week BETWEEN 0 AND 6", name="ck_schedule_day"),
        sa.CheckConstraint("end_time > start_time", name="ck_schedule_times"),
        sa.CheckConstraint("slot_minutes > 0", name="ck_schedule_slot"),
    )
    op.create_table(
        "patients",
        sa.Column("id", sa.Integer, primary_key=True),
        sa.Column("full_name", sa.String(100), nullable=False),
        sa.Column("contact", sa.String(100)),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=NOW),
    )
    op.create_table(
        "conversation_sessions",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("patient_id", sa.Integer, sa.ForeignKey("patients.id", ondelete="SET NULL")),
        sa.Column("state", postgresql.JSONB, nullable=False, server_default=sa.text("'{}'::jsonb")),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=NOW),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=NOW),
    )
    op.create_index("ix_conversation_sessions_patient_id", "conversation_sessions", ["patient_id"])
    op.create_table(
        "conversation_messages",
        sa.Column("id", sa.BigInteger, primary_key=True, autoincrement=True),
        sa.Column("session_id", postgresql.UUID(as_uuid=True),
                  sa.ForeignKey("conversation_sessions.id", ondelete="CASCADE"), nullable=False),
        sa.Column("role", sa.String(20), nullable=False),
        sa.Column("content", sa.Text, nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=NOW),
        sa.CheckConstraint("role IN ('user','assistant','system','tool')", name="ck_messages_role"),
    )
    op.create_index("ix_messages_session_id_id", "conversation_messages", ["session_id", "id"])
    op.create_table(
        "appointments",
        sa.Column("id", sa.Integer, primary_key=True),
        sa.Column("patient_id", sa.Integer, sa.ForeignKey("patients.id", ondelete="RESTRICT"), nullable=False),
        sa.Column("doctor_id", sa.Integer, sa.ForeignKey("doctors.id", ondelete="RESTRICT"), nullable=False),
        sa.Column("service_id", sa.Integer, sa.ForeignKey("services.id", ondelete="RESTRICT")),
        sa.Column("session_id", postgresql.UUID(as_uuid=True),
                  sa.ForeignKey("conversation_sessions.id", ondelete="SET NULL")),
        sa.Column("appointment_type", sa.String(30), nullable=False),
        sa.Column("reason", sa.Text),
        sa.Column("appointment_date", sa.Date, nullable=False),
        sa.Column("appointment_time", sa.Time, nullable=False),
        sa.Column("duration_minutes", sa.Integer, nullable=False),
        sa.Column("status", sa.String(20), nullable=False, server_default="booked"),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=NOW),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=NOW),
        sa.CheckConstraint("appointment_type IN ('aesthetic_treatment','general_consultation')", name="ck_appointments_type"),
        sa.CheckConstraint("status IN ('booked','cancelled','completed')", name="ck_appointments_status"),
        sa.CheckConstraint("appointment_type <> 'aesthetic_treatment' OR service_id IS NOT NULL",
                           name="ck_appointments_aesthetic_needs_service"),
        sa.CheckConstraint("duration_minutes > 0", name="ck_appointments_duration"),
    )
    op.create_index(
        "uq_appointments_doctor_slot_booked", "appointments",
        ["doctor_id", "appointment_date", "appointment_time"],
        unique=True, postgresql_where=sa.text("status = 'booked'"),
    )
    op.create_index("ix_appointments_session", "appointments", ["session_id"])
    op.create_index("ix_appointments_doctor_date", "appointments", ["doctor_id", "appointment_date"])


def downgrade() -> None:
    # Only used if you deliberately run `alembic downgrade base`.
    for table in ("appointments", "conversation_messages", "conversation_sessions", "patients",
                  "doctor_schedules", "doctor_services", "doctors", "services", "clinic_info"):
        op.drop_table(table)

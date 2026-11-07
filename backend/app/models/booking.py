"""Patients and appointments."""

import uuid
from datetime import date, datetime, time

from sqlalchemy import (
    CheckConstraint, Date, DateTime, ForeignKey, Index, Integer, String, Text, Time, func, text,
)
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base
from app.models.catalog import Doctor, Service


class Patient(Base):
    __tablename__ = "patients"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    full_name: Mapped[str] = mapped_column(String(100), nullable=False)
    contact: Mapped[str | None] = mapped_column(String(100))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)


class Appointment(Base):
    """date + time are CLINIC-LOCAL (see CLINIC_TIMEZONE); the clinic timezone is applied explicitly in code."""

    __tablename__ = "appointments"
    __table_args__ = (
        CheckConstraint(
            "appointment_type IN ('aesthetic_treatment','general_consultation')", name="ck_appointments_type"
        ),
        CheckConstraint("status IN ('booked','cancelled','completed')", name="ck_appointments_status"),
        CheckConstraint(
            "appointment_type <> 'aesthetic_treatment' OR service_id IS NOT NULL",
            name="ck_appointments_aesthetic_needs_service",
        ),
        CheckConstraint("duration_minutes > 0", name="ck_appointments_duration"),
        # The database itself refuses two ACTIVE bookings for the same doctor at the same start time.
        Index(
            "uq_appointments_doctor_slot_booked",
            "doctor_id", "appointment_date", "appointment_time",
            unique=True,
            postgresql_where=text("status = 'booked'"),
        ),
        Index("ix_appointments_session", "session_id"),
        Index("ix_appointments_doctor_date", "doctor_id", "appointment_date"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    patient_id: Mapped[int] = mapped_column(ForeignKey("patients.id", ondelete="RESTRICT"), nullable=False)
    doctor_id: Mapped[int] = mapped_column(ForeignKey("doctors.id", ondelete="RESTRICT"), nullable=False)
    service_id: Mapped[int | None] = mapped_column(ForeignKey("services.id", ondelete="RESTRICT"))
    session_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("conversation_sessions.id", ondelete="SET NULL")
    )
    appointment_type: Mapped[str] = mapped_column(String(30), nullable=False)
    reason: Mapped[str | None] = mapped_column(Text)
    appointment_date: Mapped[date] = mapped_column(Date, nullable=False)
    appointment_time: Mapped[time] = mapped_column(Time, nullable=False)
    duration_minutes: Mapped[int] = mapped_column(Integer, nullable=False)
    status: Mapped[str] = mapped_column(String(20), nullable=False, server_default="booked")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False
    )

    patient: Mapped[Patient] = relationship(lazy="selectin")
    doctor: Mapped[Doctor] = relationship(lazy="selectin")
    service: Mapped[Service | None] = relationship(lazy="selectin")

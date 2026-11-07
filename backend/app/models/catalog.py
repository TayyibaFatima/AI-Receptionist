"""Clinic information, services, doctors and doctor schedules."""

from datetime import datetime, time
from decimal import Decimal

from sqlalchemy import (
    Boolean, CheckConstraint, Column, DateTime, ForeignKey, Integer, Numeric,
    SmallInteger, String, Table, Text, Time, UniqueConstraint, func,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base

# Which doctor performs which service (many-to-many).
doctor_services = Table(
    "doctor_services",
    Base.metadata,
    Column("doctor_id", ForeignKey("doctors.id", ondelete="CASCADE"), primary_key=True),
    Column("service_id", ForeignKey("services.id", ondelete="CASCADE"), primary_key=True),
)


class ClinicInfo(Base):
    __tablename__ = "clinic_info"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    clinic_name: Mapped[str] = mapped_column(String(150), nullable=False)
    address: Mapped[str | None] = mapped_column(Text)
    phone: Mapped[str | None] = mapped_column(String(50))
    email: Mapped[str | None] = mapped_column(String(150))
    opening_hours: Mapped[str | None] = mapped_column(Text)
    general_info: Mapped[str | None] = mapped_column(Text)
    currency: Mapped[str] = mapped_column(String(10), nullable=False, server_default="PKR")
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False
    )


class Service(Base):
    __tablename__ = "services"
    __table_args__ = (
        CheckConstraint(
            "category IN ('aesthetic_treatment','general_consultation')", name="ck_services_category"
        ),
        CheckConstraint("price IS NULL OR price >= 0", name="ck_services_price"),
        CheckConstraint("duration_minutes IS NULL OR duration_minutes > 0", name="ck_services_duration"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    name: Mapped[str] = mapped_column(String(150), unique=True, nullable=False)
    category: Mapped[str] = mapped_column(String(30), nullable=False)
    description: Mapped[str | None] = mapped_column(Text)
    price: Mapped[Decimal | None] = mapped_column(Numeric(10, 2))
    duration_minutes: Mapped[int | None] = mapped_column(Integer)
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, server_default="true")


class Doctor(Base):
    __tablename__ = "doctors"
    __table_args__ = (CheckConstraint("consultation_fee IS NULL OR consultation_fee >= 0", name="ck_doctors_fee"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    full_name: Mapped[str] = mapped_column(String(150), nullable=False)
    specialization: Mapped[str] = mapped_column(String(100), nullable=False)
    profile_description: Mapped[str | None] = mapped_column(Text)
    consultation_fee: Mapped[Decimal | None] = mapped_column(Numeric(10, 2))
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, server_default="true")

    services: Mapped[list[Service]] = relationship(secondary=doctor_services, lazy="selectin")


class DoctorSchedule(Base):
    """Weekly working hours. day_of_week: 0 = Monday ... 6 = Sunday."""

    __tablename__ = "doctor_schedules"
    __table_args__ = (
        UniqueConstraint("doctor_id", "day_of_week", "start_time", name="uq_schedule_doctor_day_start"),
        CheckConstraint("day_of_week BETWEEN 0 AND 6", name="ck_schedule_day"),
        CheckConstraint("end_time > start_time", name="ck_schedule_times"),
        CheckConstraint("slot_minutes > 0", name="ck_schedule_slot"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    doctor_id: Mapped[int] = mapped_column(ForeignKey("doctors.id", ondelete="CASCADE"), nullable=False)
    day_of_week: Mapped[int] = mapped_column(SmallInteger, nullable=False)
    start_time: Mapped[time] = mapped_column(Time, nullable=False)
    end_time: Mapped[time] = mapped_column(Time, nullable=False)
    slot_minutes: Mapped[int] = mapped_column(Integer, nullable=False, server_default="30")
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, server_default="true")

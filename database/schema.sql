-- Luméra Aesthetics AI Receptionist - PostgreSQL schema
-- Equivalent to Alembic migration 0001. Use EITHER this file OR `alembic upgrade head`, not both.
-- Safe: uses CREATE ... IF NOT EXISTS and never drops anything.

CREATE TABLE IF NOT EXISTS clinic_info (
    id             SERIAL PRIMARY KEY,
    clinic_name    VARCHAR(150) NOT NULL,
    address        TEXT,
    phone          VARCHAR(50),
    email          VARCHAR(150),
    opening_hours  TEXT,
    general_info   TEXT,
    currency       VARCHAR(10) NOT NULL DEFAULT 'PKR',
    updated_at     TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE TABLE IF NOT EXISTS services (
    id                SERIAL PRIMARY KEY,
    name              VARCHAR(150) NOT NULL UNIQUE,
    category          VARCHAR(30) NOT NULL,
    description       TEXT,
    price             NUMERIC(10,2),
    duration_minutes  INTEGER,
    is_active         BOOLEAN NOT NULL DEFAULT true,
    CONSTRAINT ck_services_category CHECK (category IN ('aesthetic_treatment','general_consultation')),
    CONSTRAINT ck_services_price CHECK (price IS NULL OR price >= 0),
    CONSTRAINT ck_services_duration CHECK (duration_minutes IS NULL OR duration_minutes > 0)
);

CREATE TABLE IF NOT EXISTS doctors (
    id                   SERIAL PRIMARY KEY,
    full_name            VARCHAR(150) NOT NULL,
    specialization       VARCHAR(100) NOT NULL,
    profile_description  TEXT,
    consultation_fee     NUMERIC(10,2),
    is_active            BOOLEAN NOT NULL DEFAULT true,
    CONSTRAINT ck_doctors_fee CHECK (consultation_fee IS NULL OR consultation_fee >= 0)
);

CREATE TABLE IF NOT EXISTS doctor_services (
    doctor_id   INTEGER NOT NULL REFERENCES doctors(id) ON DELETE CASCADE,
    service_id  INTEGER NOT NULL REFERENCES services(id) ON DELETE CASCADE,
    PRIMARY KEY (doctor_id, service_id)
);

-- day_of_week: 0 = Monday ... 6 = Sunday
CREATE TABLE IF NOT EXISTS doctor_schedules (
    id            SERIAL PRIMARY KEY,
    doctor_id     INTEGER NOT NULL REFERENCES doctors(id) ON DELETE CASCADE,
    day_of_week   SMALLINT NOT NULL,
    start_time    TIME NOT NULL,
    end_time      TIME NOT NULL,
    slot_minutes  INTEGER NOT NULL DEFAULT 30,
    is_active     BOOLEAN NOT NULL DEFAULT true,
    CONSTRAINT uq_schedule_doctor_day_start UNIQUE (doctor_id, day_of_week, start_time),
    CONSTRAINT ck_schedule_day CHECK (day_of_week BETWEEN 0 AND 6),
    CONSTRAINT ck_schedule_times CHECK (end_time > start_time),
    CONSTRAINT ck_schedule_slot CHECK (slot_minutes > 0)
);

CREATE TABLE IF NOT EXISTS patients (
    id          SERIAL PRIMARY KEY,
    full_name   VARCHAR(100) NOT NULL,
    contact     VARCHAR(100),
    created_at  TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE TABLE IF NOT EXISTS conversation_sessions (
    id          UUID PRIMARY KEY,
    patient_id  INTEGER REFERENCES patients(id) ON DELETE SET NULL,
    state       JSONB NOT NULL DEFAULT '{}'::jsonb,
    created_at  TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at  TIMESTAMPTZ NOT NULL DEFAULT now()
);
CREATE INDEX IF NOT EXISTS ix_conversation_sessions_patient_id ON conversation_sessions (patient_id);

CREATE TABLE IF NOT EXISTS conversation_messages (
    id          BIGSERIAL PRIMARY KEY,
    session_id  UUID NOT NULL REFERENCES conversation_sessions(id) ON DELETE CASCADE,
    role        VARCHAR(20) NOT NULL,
    content     TEXT NOT NULL,
    created_at  TIMESTAMPTZ NOT NULL DEFAULT now(),
    CONSTRAINT ck_messages_role CHECK (role IN ('user','assistant','system','tool'))
);
CREATE INDEX IF NOT EXISTS ix_messages_session_id_id ON conversation_messages (session_id, id);

-- appointment_date / appointment_time are CLINIC-LOCAL (see CLINIC_TIMEZONE in the app).
CREATE TABLE IF NOT EXISTS appointments (
    id                SERIAL PRIMARY KEY,
    patient_id        INTEGER NOT NULL REFERENCES patients(id) ON DELETE RESTRICT,
    doctor_id         INTEGER NOT NULL REFERENCES doctors(id) ON DELETE RESTRICT,
    service_id        INTEGER REFERENCES services(id) ON DELETE RESTRICT,   -- NULL allowed for general consultations
    session_id        UUID REFERENCES conversation_sessions(id) ON DELETE SET NULL,
    appointment_type  VARCHAR(30) NOT NULL,
    reason            TEXT,
    appointment_date  DATE NOT NULL,
    appointment_time  TIME NOT NULL,
    duration_minutes  INTEGER NOT NULL,
    status            VARCHAR(20) NOT NULL DEFAULT 'booked',
    created_at        TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at        TIMESTAMPTZ NOT NULL DEFAULT now(),
    CONSTRAINT ck_appointments_type CHECK (appointment_type IN ('aesthetic_treatment','general_consultation')),
    CONSTRAINT ck_appointments_status CHECK (status IN ('booked','cancelled','completed')),
    CONSTRAINT ck_appointments_aesthetic_needs_service
        CHECK (appointment_type <> 'aesthetic_treatment' OR service_id IS NOT NULL),
    CONSTRAINT ck_appointments_duration CHECK (duration_minutes > 0)
);
-- The database refuses two ACTIVE bookings for the same doctor at the same start time.
CREATE UNIQUE INDEX IF NOT EXISTS uq_appointments_doctor_slot_booked
    ON appointments (doctor_id, appointment_date, appointment_time) WHERE status = 'booked';
CREATE INDEX IF NOT EXISTS ix_appointments_session ON appointments (session_id);
CREATE INDEX IF NOT EXISTS ix_appointments_doctor_date ON appointments (doctor_id, appointment_date);

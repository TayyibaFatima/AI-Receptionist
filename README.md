# Luméra Aesthetics: AI Receptionist

A working AI receptionist for an aesthetic clinic. Visitors chat with it to learn about treatments, meet the doctors, and **book, view, reschedule and cancel appointments**. Everything (services, doctors, schedules, appointments, chat history) lives in **PostgreSQL**. The AI never invents data: it asks the backend through *tools*.

> All clinic data in `database/seed.sql` is **demonstration data** (sample doctors, prices, hours). Replace it with real information before real use.

## Features
- Chat with persistent, per-visitor sessions (stored in PostgreSQL)
- Services, doctors and schedules read from the database
- Real availability calculated by the backend (working hours + existing bookings + clinic timezone)
- Aesthetic treatments **and** general consultations (a consultation needs no treatment)
- **Explicit confirmation enforced by the backend**, not just the AI
- Double-booking prevention (row locking + a partial unique index)
- View / reschedule / cancel, from chat or from the "My appointments" panel
- Emergency-message safety reply, rate limiting, input validation, CORS
- Responsive luxury-clinic UI: cards for doctors, treatments, slots and booking summary

## Tech stack
Backend: Python 3.13, FastAPI, SQLAlchemy 2, Psycopg 3, Alembic, Pydantic, Groq API (tool calling), Uvicorn.
Frontend: React + Vite (JavaScript, CSS, Fetch). Database: PostgreSQL. Hosting: Vercel (frontend), FastAPI Cloud (backend).

## Architecture (simple version)
```
Browser (React)  ──HTTP──►  FastAPI routes ──► services (business rules) ──► PostgreSQL
                                  │
                                  └─► AI agent ──► Groq (LLM)
                                         ▲  │  asks "call get_doctors", "call create_appointment"...
                                         └──┘  tools/executor.py runs them with validation
```
1. The browser sends your message plus a **session ID** (a random UUID kept in `localStorage`).
2. The backend saves the message, then asks the Groq model what to do.
3. The model can only *request tools*. `tools/executor.py` validates the arguments and calls normal Python service functions. The model never touches SQL.
4. Tool results go back to the model, which writes the friendly reply. Tools also return "cards" the UI draws (doctor cards, slot buttons, booking summary).

```
AI-Receptionist/
├── backend/
│   ├── app/
│   │   ├── main.py  config.py  database.py
│   │   ├── models/      SQLAlchemy tables
│   │   ├── schemas/     Pydantic request/response models
│   │   ├── routes/      REST endpoints (thin)
│   │   ├── services/    business rules: availability, booking, sessions, confirmation
│   │   ├── tools/       tool schemas for the AI + validated executor
│   │   ├── agents/      system prompt + Groq loop
│   │   └── utils/       rate limiter, session header
│   ├── alembic/         migrations     scripts/run_sql.py     tests/
│   └── requirements.txt  .env.example
├── frontend/            React app (src/components, hooks, services)
└── database/            schema.sql  seed.sql
```

## Setup on Windows (PowerShell)

### 1. Database
```powershell
psql -U postgres -h localhost
```
```sql
CREATE DATABASE ai_receptionist;
CREATE DATABASE ai_receptionist_test;   -- used only by automated tests
\q
```
(pgAdmin: right-click Databases → Create → Database.)

### 2. Backend
```powershell
cd backend
py -3.13 -m venv venv
.\venv\Scripts\Activate.ps1          # if blocked: Set-ExecutionPolicy -Scope CurrentUser RemoteSigned
python -m pip install --upgrade pip
pip install -r requirements-dev.txt
copy .env.example .env
```
Edit `backend/.env`: set `DATABASE_URL`, `TEST_DATABASE_URL`, `GROQ_API_KEY` (free key: https://console.groq.com/keys) and `GROQ_MODEL` (any Groq model that supports tool calling; see https://console.groq.com/docs/models). If your DB password has special characters, URL-encode them (`@`→`%40`, `#`→`%23`).

Create the tables (safe: never drops data) and load the demo data:
```powershell
alembic upgrade head
python scripts/run_sql.py ../database/seed.sql
```
Prefer plain SQL? `psql -U postgres -d ai_receptionist -f ../database/schema.sql` creates the same tables (use it **instead of** Alembic, not both).

Verify in `psql`/pgAdmin:
```sql
\c ai_receptionist
SELECT full_name, specialization FROM doctors;
SELECT name, price FROM services;
SELECT * FROM doctor_schedules LIMIT 5;
```
Run the API:
```powershell
uvicorn app.main:app --reload
```
Open http://127.0.0.1:8000/health (should show `"database":"connected"`) and http://127.0.0.1:8000/docs.

### 3. Frontend
```powershell
cd ..\frontend
npm install
copy .env.example .env.local      # VITE_API_URL=http://localhost:8000
npm run dev
```
Open http://localhost:5173.

## API endpoints
| Method | Path | Purpose |
|---|---|---|
| GET | `/`, `/health` | Welcome; API + database check |
| GET | `/clinic`, `/services`, `/doctors` | Clinic info; services (`?category=`); doctors (`?service_id=`) |
| GET | `/doctors/{id}/schedule` | Weekly working hours |
| GET | `/availability?doctor_id=&date=YYYY-MM-DD&service_id=` | Free slots |
| POST | `/chat` | Send a message `{session_id, message}` |
| GET | `/chat/history` | Visitor's saved conversation |
| POST | `/appointments` | Book (body needs `"confirmed": true`) |
| GET | `/appointments`, `/appointments/{id}` | The visitor's own appointments |
| PATCH | `/appointments/{id}` | Reschedule (`confirmed: true`) |
| DELETE | `/appointments/{id}?confirmed=true` | Cancel (status becomes `cancelled`; record kept) |

Appointment endpoints require the header `X-Session-ID: <uuid>`.

## AI tool calling
The model is given nine tools: `get_clinic_information`, `get_services`, `get_doctors`, `get_doctor_schedule`, `check_availability`, `create_appointment`, `get_patient_appointments`, `reschedule_appointment`, `cancel_appointment`. Each call is validated with Pydantic, then executed by backend code. Errors are returned to the model as `{"ok": false, "error": ...}` so it can explain them politely.

## Booking workflow & how confirmation is enforced
1. The AI collects details one question at a time (type → treatment/consultation → doctor → date → slot → name).
2. It calls `create_appointment` with `confirmed=false`. The backend validates everything (doctor active, service active, doctor offers the service, working hours, not in the past, slot free), **stores a pending action in the session**, and returns a summary. The UI shows a summary card.
3. The patient answers. When the AI calls the tool again with `confirmed=true`, the backend only proceeds if **(a)** the pending summary matches exactly, **(b)** the patient sent a *new* message after the summary, and **(c)** that message is a clear "yes" (a message like "yes but change the time" is rejected).
4. Inside one database transaction the doctor row is locked, availability is re-checked, and the appointment is inserted. A partial unique index `(doctor, date, time) WHERE status='booked'` is the last line of defence. Only after commit does the AI see `status: booked`.
5. If the model claims a booking that did not happen, the backend replaces the reply.

Times are stored as clinic-local date + time; `CLINIC_TIMEZONE` (default `Asia/Karachi`) is applied explicitly when checking "in the past".

## Testing
```powershell
cd backend
pytest -q
```
Tests use `TEST_DATABASE_URL` (the name must end in `_test`; the tests wipe it). They cover: DB connection, services/doctors/schedules, availability, successful booking, duplicates and overlaps, concurrent booking race, no-confirmation, invalid doctor/service, past/outside-hours, reschedule, cancel, session isolation, the chat tool flow with a scripted fake Groq (no API key needed), Groq failure and rate limiting.

### Manual test of the real conversation (needs a real Groq key)
1. "Hi, I want to book an appointment" → it asks aesthetic vs consultation.
2. Choose "aesthetic treatment" → pick HydraFacial → pick a doctor card → give a date → click a slot → give your name.
3. A summary card appears and it asks "Would you like me to confirm this appointment?". Type **"actually, change the time"**: nothing is booked, a new summary appears.
4. Click **Confirm appointment**: the card turns green, and "My appointments" shows it. Check in SQL: `SELECT * FROM appointments;`
5. Open a private window (a new visitor), try the same slot: it's gone. "My appointments" there is empty.
6. Use Reschedule and Cancel in the panel, and by chat ("cancel my appointment").
7. Type "I have chest pain": you get an emergency message and the AI is not called.

## Deployment
Do each step yourself; nothing here has been deployed for you.

### Production PostgreSQL
Create a hosted PostgreSQL database (e.g. Neon, Supabase, Railway, Render; check current free tiers) and copy its connection string. `postgres://` / `postgresql://` URLs are auto-converted to the Psycopg 3 driver. If the host requires SSL, append `?sslmode=require`. Create tables and seed from your PC, pointing at the production URL:
```powershell
$env:DATABASE_URL="postgresql://USER:PASS@HOST/DBNAME?sslmode=require"
alembic upgrade head
python scripts/run_sql.py ../database/seed.sql     # demo data; replace with real data for production
```

### Backend → FastAPI Cloud
```powershell
cd backend
fastapi login
fastapi deploy
fastapi cloud env set DATABASE_URL "postgresql://USER:PASS@HOST/DBNAME?sslmode=require"
fastapi cloud env set GROQ_API_KEY "your_key"
fastapi cloud env set GROQ_MODEL "your_model"
fastapi cloud env set CLINIC_TIMEZONE "Asia/Karachi"
fastapi cloud env set FRONTEND_URL "https://your-frontend.vercel.app"
fastapi deploy
```
(`pyproject.toml` already sets the app entrypoint. If a command differs in your CLI version, check `fastapi cloud --help` or the FastAPI Cloud docs, which are the source of truth.) Then open `https://<your-app>/health` and `/docs`, and run the manual test above against it.
`FRONTEND_URL` may contain several comma-separated origins (e.g. production + a preview URL).

### Frontend → Vercel
1. Push to GitHub. In Vercel: **Add New → Project → import the repo**.
2. Set **Root Directory** to `frontend` (framework: Vite).
3. Add environment variable `VITE_API_URL` = your backend URL (no trailing slash).
4. Deploy, then test on desktop and phone. If chat fails with a CORS error, re-check `FRONTEND_URL` on the backend.

## Security limitations (please read)
- **No login.** A visitor "owns" appointments through their random session UUID (stored in the browser). Anyone who has that UUID can act as that visitor, and clearing browser storage loses access. Fine for a demo; for production add patient authentication (e.g. phone OTP) before showing personal details.
- The yes/no check is a keyword rule plus pending-summary matching: robust against the AI misbehaving, but not a legal consent record.
- The rate limiter is in-memory per server instance (and trusts `X-Forwarded-For`). For several instances use a shared store such as Redis.
- Only the patient's name, optional contact and reason are stored; chat text is stored too. Don't type sensitive medical details, and add a retention/deletion policy before real use.
- The AI gives no medical advice, but LLMs can still make mistakes; keep staff contact details accurate.
- Never commit `.env`; rotate any key that leaks.

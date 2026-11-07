"""FastAPI application entry point."""

import logging

from fastapi import Depends, FastAPI, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from sqlalchemy import text
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session

from app.config import get_settings
from app.database import get_db
from app.routes import appointments, chat, clinic
from app.services.errors import ServiceError

logging.basicConfig(level=logging.INFO, format="%(levelname)s %(name)s: %(message)s")
logger = logging.getLogger(__name__)
settings = get_settings()

app = FastAPI(
    title=f"{settings.clinic_name} AI Receptionist API",
    version="1.0.0",
    description="Backend for the Luméra Aesthetics AI receptionist.",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins,
    allow_credentials=False,  # we use the X-Session-ID header, not cookies
    allow_methods=["GET", "POST", "PATCH", "DELETE", "OPTIONS"],
    allow_headers=["*"],
)


@app.exception_handler(ServiceError)
async def service_error_handler(request: Request, exc: ServiceError):
    return JSONResponse(status_code=exc.status_code, content={"detail": exc.message, "code": exc.code})


@app.exception_handler(SQLAlchemyError)
async def database_error_handler(request: Request, exc: SQLAlchemyError):
    logger.exception("Database error")
    return JSONResponse(status_code=503, content={"detail": "A database error occurred. Please try again."})


app.include_router(clinic.router)
app.include_router(chat.router)
app.include_router(appointments.router)


@app.get("/", tags=["system"])
def root() -> dict:
    return {"message": f"Welcome to the {settings.clinic_name} AI Receptionist API", "docs": "/docs", "health": "/health"}


@app.get("/health", tags=["system"])
def health(db: Session = Depends(get_db)) -> dict:
    """Confirms the API is running AND can reach PostgreSQL."""
    try:
        db.execute(text("SELECT 1"))
    except SQLAlchemyError:
        logger.exception("Database health check failed")
        raise HTTPException(status_code=503, detail="Database connection failed")
    return {"status": "ok", "database": "connected"}

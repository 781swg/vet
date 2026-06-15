from fastapi import APIRouter, Response
from prometheus_client import CONTENT_TYPE_LATEST, Counter, Gauge, generate_latest
from sqlalchemy import select, text

from app.core.config import get_settings
from app.db.models import Business, Channel, DoctorUser
from app.db.session import SessionLocal


router = APIRouter(tags=["monitoring"])

APP_INFO = Gauge("vet_ai_manager_info", "Application info", ["env"])
READY_CHECKS = Counter("vet_ai_manager_ready_checks_total", "Readiness checks", ["status"])


@router.get("/ready")
async def ready() -> dict:
    checks: dict[str, str] = {}
    settings = get_settings()
    try:
        async with SessionLocal() as session:
            await session.execute(text("select 1"))
            business = await session.get(Business, settings.default_business_id)
            telegram_channel = (
                await session.execute(
                    select(Channel).where(Channel.business_id == settings.default_business_id, Channel.channel_type == "telegram")
                )
            ).scalars().first()
            doctor_user = (
                await session.execute(select(DoctorUser).where(DoctorUser.business_id == settings.default_business_id, DoctorUser.is_active.is_(True)))
            ).scalars().first()
        checks["database"] = "ok"
        checks["business"] = "ok" if business else f"business_id={settings.default_business_id} not found. Run seed.py"
        checks["telegram_channel"] = "ok" if telegram_channel else "telegram channel not found. Run seed.py"
        checks["doctor_user"] = "ok" if doctor_user else "doctor user not found. Set DOCTOR_TELEGRAM_USER_ID and run seed.py"
    except Exception as exc:
        checks["database"] = f"error: {exc}"

    if settings.redis_url:
        try:
            from redis import Redis

            Redis.from_url(settings.redis_url).ping()
            checks["redis"] = "ok"
        except Exception as exc:
            checks["redis"] = f"error: {exc}"
    else:
        checks["redis"] = "not_configured"

    status = "ok" if all(value in {"ok", "not_configured"} for value in checks.values()) else "error"
    READY_CHECKS.labels(status=status).inc()
    return {"status": status, "checks": checks}


@router.get("/metrics")
async def metrics() -> Response:
    settings = get_settings()
    APP_INFO.labels(env=settings.app_env).set(1)
    return Response(generate_latest(), media_type=CONTENT_TYPE_LATEST)

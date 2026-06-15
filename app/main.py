from pathlib import Path

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles

from app.api.routes import admin, health, monitoring, site, webhooks_doctor_telegram, webhooks_max, webhooks_telegram, webhooks_vk, webhooks_whatsapp
from app.core.config import get_settings
from app.core.logging import configure_logging


settings = get_settings()
configure_logging(settings.log_level)

app = FastAPI(title="Vet AI Manager", version="0.1.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.site_cors_origins,
    allow_credentials=False,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(health.router)
app.include_router(monitoring.router)
app.include_router(site.router)
app.include_router(webhooks_telegram.router)
app.include_router(webhooks_doctor_telegram.router)
app.include_router(webhooks_whatsapp.router)
app.include_router(webhooks_max.router)
app.include_router(webhooks_vk.router)
app.include_router(admin.router)

site_dir = Path(__file__).resolve().parents[1] / "site"
if site_dir.exists():
    app.mount("/", StaticFiles(directory=site_dir, html=True), name="site")

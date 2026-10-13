"""
DesignLint backend entrypoint: app wiring, CORS, and the API routers.
"""
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.config.settings import settings
from app.routes import health, analyze

app = FastAPI(
    title="DesignLint API",
    description="Backend for DesignLint - an AI-assisted UI design auditor.",
    version="0.1.0",
)

# Only the origins listed in CORS_ORIGINS may call the API from a browser.
# No cookies or auth headers are used, so credentials are not enabled, and
# only the methods this API actually serves are allowed.
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.CORS_ORIGINS,
    allow_credentials=False,
    allow_methods=["GET", "POST", "OPTIONS"],
    allow_headers=["*"],
)

app.include_router(health.router, prefix="/api")
app.include_router(analyze.router, prefix="/api")

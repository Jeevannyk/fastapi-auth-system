import logging
import os

from fastapi import Depends, FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from slowapi.errors import RateLimitExceeded
from slowapi.middleware import SlowAPIMiddleware
from starlette.middleware.httpsredirect import HTTPSRedirectMiddleware
from starlette.requests import Request
from starlette.responses import JSONResponse

from .config import get_settings
from .deps import current_user
from .models import User
from .rate_limit import limiter
from .routes import auth, devices, oauth, pages, qr
from .schemas import UserResponse

logger = logging.getLogger(__name__)


def create_app() -> FastAPI:
    settings = get_settings()
    app = FastAPI(
        title="Cipher — Passwordless QR Auth",
        version="2.0.0",
        description="Secure, reusable identity provider using dynamic QR-code authentication.",
    )

    app.state.limiter = limiter
    app.add_middleware(SlowAPIMiddleware)
    app.add_exception_handler(RateLimitExceeded, _rate_limit_handler)

    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.allowed_origins,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    if settings.is_production:
        app.add_middleware(HTTPSRedirectMiddleware)

    frontend_dir = os.path.join(
        os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "frontend"
    )
    app.mount("/static", StaticFiles(directory=frontend_dir), name="static")

    app.include_router(pages.router)
    app.include_router(auth.router)
    app.include_router(qr.router)
    app.include_router(devices.router)
    app.include_router(oauth.router)

    @app.get("/api/auth/me", response_model=UserResponse, tags=["auth"])
    def me(user: User = Depends(current_user)):
        return UserResponse.model_validate(user)

    @app.get("/health", tags=["meta"])
    def health():
        return {"status": "ok"}

    return app


def _rate_limit_handler(request: Request, exc: RateLimitExceeded) -> JSONResponse:
    return JSONResponse(status_code=429, content={"detail": "Too many requests"})


app = create_app()

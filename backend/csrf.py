"""Double-submit-cookie CSRF protection.

The browser flow authenticates with HttpOnly cookies (``access_token`` and
``device_token``), which are sent automatically by the browser and are therefore
vulnerable to cross-site request forgery. We defend with the standard
double-submit pattern:

  * A non-HttpOnly ``csrf_token`` cookie is issued to every browser.
  * JavaScript reads it and echoes it back in the ``X-CSRF-Token`` header on
    every state-changing request.
  * This middleware rejects any unsafe request that carries one of our auth
    cookies unless the header matches the cookie.

Requests with no auth cookie (public endpoints, and server-to-server calls such
as the OAuth token endpoint authenticated by ``client_secret``) are not
CSRF-vulnerable and are left untouched.
"""

import hmac
import secrets

from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import JSONResponse

from .deps import ACCESS_COOKIE, DEVICE_COOKIE

CSRF_COOKIE = "csrf_token"
ENROLLED_COOKIE = "device_enrolled"  # readable flag so the UI can detect enrollment
CSRF_HEADER = "X-CSRF-Token"

SAFE_METHODS = {"GET", "HEAD", "OPTIONS", "TRACE"}
AUTH_COOKIES = (ACCESS_COOKIE, DEVICE_COOKIE)


def new_csrf_token() -> str:
    return secrets.token_urlsafe(32)


class CSRFMiddleware(BaseHTTPMiddleware):
    def __init__(self, app, cookie_secure: bool = False):
        super().__init__(app)
        self.cookie_secure = cookie_secure

    async def dispatch(self, request: Request, call_next):
        if request.method not in SAFE_METHODS:
            has_auth_cookie = any(c in request.cookies for c in AUTH_COOKIES)
            if has_auth_cookie:
                cookie_token = request.cookies.get(CSRF_COOKIE)
                header_token = request.headers.get(CSRF_HEADER)
                if (
                    not cookie_token
                    or not header_token
                    or not hmac.compare_digest(cookie_token, header_token)
                ):
                    return JSONResponse(
                        status_code=403,
                        content={"detail": "CSRF token missing or invalid"},
                    )

        response = await call_next(request)

        # Ensure every browser ends up with a CSRF token for future requests.
        if CSRF_COOKIE not in request.cookies:
            response.set_cookie(
                CSRF_COOKIE,
                new_csrf_token(),
                httponly=False,
                secure=self.cookie_secure,
                samesite="lax",
                path="/",
            )
        return response

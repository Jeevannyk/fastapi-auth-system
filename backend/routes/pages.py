import os

from fastapi import APIRouter
from fastapi.responses import FileResponse, RedirectResponse

router = APIRouter(tags=["pages"])

BASE_DIR = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
FRONTEND_DIR = os.path.join(BASE_DIR, "frontend")


def _page(name: str) -> FileResponse:
    return FileResponse(os.path.join(FRONTEND_DIR, name))


@router.get("/", include_in_schema=False)
def root():
    return RedirectResponse("/login")


@router.get("/login", include_in_schema=False)
def login_page():
    return _page("login.html")


@router.get("/register", include_in_schema=False)
def register_page():
    return _page("register.html")


@router.get("/scan", include_in_schema=False)
def scan_page():
    return _page("scan.html")


@router.get("/home", include_in_schema=False)
def home_page():
    return _page("home.html")

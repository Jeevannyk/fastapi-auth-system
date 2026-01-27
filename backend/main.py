from fastapi import FastAPI, HTTPException, Depends
from fastapi.responses import FileResponse, RedirectResponse
from fastapi.staticfiles import StaticFiles
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, EmailStr
from sqlalchemy.orm import Session
import uuid
import qrcode
import os
import re
import sys
import logging
from datetime import datetime, timedelta, timezone
from .database import get_db, init_db, SessionLocal
from .models import User, Session as DBSession
from .security import hash_password, verify_password, create_token, verify_token

# Configure logging
logger = logging.getLogger(__name__)
logging.basicConfig(level=logging.INFO)

app = FastAPI(title="Antigravity Secure Access")

# -------------------- STATIC FILES --------------------
BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
FRONTEND_DIR = os.path.join(BASE_DIR, "frontend")

app.mount("/static", StaticFiles(directory=FRONTEND_DIR), name="static")

# -------------------- CORS --------------------
# Restrict CORS in production - use specific origins
ALLOWED_ORIGINS = [origin.strip() for origin in os.getenv("ALLOWED_ORIGINS", "http://localhost:8000,http://127.0.0.1:8000").split(",") if origin.strip()]
app.add_middleware(
    CORSMiddleware,
    allow_origins=ALLOWED_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# -------------------- INITIALIZE DATABASE --------------------
try:
    init_db()
except Exception as e:
    logger.error(f"Database initialization failed: {e}", exc_info=True)
    sys.exit(1)

# -------------------- MODELS --------------------
class SignupRequest(BaseModel):
    full_name: str
    email: EmailStr
    access_key: str
    verify_key: str

class LoginRequest(BaseModel):
    email: EmailStr
    access_key: str

class LoginResponse(BaseModel):
    message: str
    access_token: str
    next: str

class FingerprintRequest(BaseModel):
    email: EmailStr

# -------------------- HELPERS --------------------
def is_expired(created_at: datetime, timeout_minutes: int = 5) -> bool:
    """Check if session has expired"""
    try:
        now = datetime.now(timezone.utc)
        # Make created_at timezone-aware if it isn't
        if created_at.tzinfo is None:
            created_at = created_at.replace(tzinfo=timezone.utc)
        return now - created_at > timedelta(minutes=timeout_minutes)
    except Exception as e:
        print(f"Error checking expiration: {e}")
        return True

def validate_uuid(session_id: str) -> bool:
    """Validate that session_id is a valid UUID to prevent path traversal"""
    try:
        # Also check for path traversal patterns
        if ".." in session_id or "/" in session_id or "\\" in session_id:
            return False
        uuid.UUID(session_id)
        return True
    except ValueError:
        return False

def cleanup_old_qrs():
    """Delete QR code files older than 10 minutes"""
    qr_dir = "qrs"
    if os.path.exists(qr_dir):
        cutoff = datetime.now(timezone.utc) - timedelta(minutes=10)
        for file in os.listdir(qr_dir):
            file_path = os.path.join(qr_dir, file)
            try:
                if os.path.isfile(file_path):
                    file_time = datetime.fromtimestamp(os.path.getmtime(file_path), tz=timezone.utc)
                    if file_time < cutoff:
                        os.remove(file_path)
            except Exception as e:
                print(f"Error cleaning up QR file {file}: {e}")

# -------------------- ROUTES --------------------

@app.get("/")
def root():
    return RedirectResponse(url="/login")

@app.get("/login")
def login_page():
    return FileResponse(os.path.join(FRONTEND_DIR, "login.html"))

@app.get("/signup-page")
def signup_page():
    return FileResponse(os.path.join(FRONTEND_DIR, "signup.html"))

@app.get("/home")
def home_page():
    return FileResponse(os.path.join(FRONTEND_DIR, "home.html"))

@app.get("/health")
def health():
    return {"status": "ok"}


# ---------- SIGNUP ----------
@app.post("/signup")
def signup(data: SignupRequest, db: Session = Depends(get_db)):
    if data.access_key != data.verify_key:
        raise HTTPException(status_code=400, detail="Access keys do not match")
    
    # Check if user already exists
    existing_user = db.query(User).filter(User.email == data.email).first()
    if existing_user:
        raise HTTPException(status_code=400, detail="Email already registered")
    
    # Create new user with hashed password
    new_user = User(
        full_name=data.full_name,
        email=data.email,
        password_hash=hash_password(data.access_key)
    )
    
    try:
        db.add(new_user)
        db.commit()
        db.refresh(new_user)
    except Exception as e:
        db.rollback()
        logger.exception("Failed to create user")
        raise HTTPException(status_code=500, detail="Failed to create user")

    return {
        "message": "Access initialized",
        "next": "login"
    }

# ---------- LOGIN ----------
@app.post("/login", response_model=LoginResponse)
def login(data: LoginRequest, db: Session = Depends(get_db)):
    # Find user by email
    user = db.query(User).filter(User.email == data.email).first()
    
    if not user or not verify_password(data.access_key, user.password_hash):
        raise HTTPException(status_code=401, detail="Invalid credentials")
    
    # Create access token
    access_token = create_token(user.id)

    return LoginResponse(
        message="Credentials verified",
        access_token=access_token,
        next="fingerprint"
    )

# ---------- FINGERPRINT (SIMULATED) ----------
@app.post("/fingerprint")
def fingerprint(data: FingerprintRequest, token: dict = Depends(verify_token), db: Session = Depends(get_db)):
    # Get user from token
    user_id = int(token.get("user_id"))
    user = db.query(User).filter(User.id == user_id).first()
    
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    
    # Verify token's user matches requested email (optional extra security check)
    if user.email != data.email:
        raise HTTPException(status_code=403, detail="Token does not match requested email")
    
    session_id = str(uuid.uuid4())
    
    # Delete any existing sessions for this user to prevent duplicates
    db.query(DBSession).filter(DBSession.user_id == user_id).delete()
    
    # Insert new session
    new_session = DBSession(
        session_id=session_id,
        user_id=user_id,
        created_at=datetime.now(timezone.utc)
    )
    
    try:
        db.add(new_session)
        db.commit()
    except Exception as e:
        db.rollback()
        logger.exception("Failed to create session")
        raise HTTPException(status_code=500, detail="Failed to create session")
    
    # Cleanup old QR files
    cleanup_old_qrs()

    return {
        "message": "Biometric verified",
        "session_id": session_id,
        "next": "qr"
    }

# ---------- QR CODE ----------
@app.get("/qr/{session_id}")
def qr(session_id: str, db: Session = Depends(get_db)):
    # Validate UUID format to prevent path traversal
    if not validate_uuid(session_id):
        raise HTTPException(status_code=400, detail="Invalid session ID format")
    
    # Validate session exists and hasn't expired
    session = db.query(DBSession).filter(DBSession.session_id == session_id).first()
    
    if not session:
        raise HTTPException(status_code=404, detail="Session not found")
    
    if is_expired(session.created_at):
        raise HTTPException(status_code=403, detail="Session expired")
    
    qr_dir = "qrs"
    os.makedirs(qr_dir, exist_ok=True)

    payload = f"antigravity://connect/{session_id}"
    path = os.path.join(qr_dir, f"{session_id}.png")

    img = qrcode.make(payload)
    img.save(path)

    return {
        "qr_image": path,
        "payload": payload
    }

# ---------- SERVE QR IMAGE ----------
@app.get("/qr-image/{session_id}")
def get_qr_image(session_id: str, db: Session = Depends(get_db)):
    # Validate UUID format to prevent path traversal
    if not validate_uuid(session_id):
        raise HTTPException(status_code=400, detail="Invalid session ID format")
    
    # Validate session exists and hasn't expired
    session = db.query(DBSession).filter(DBSession.session_id == session_id).first()
    
    if not session:
        raise HTTPException(status_code=404, detail="Session not found")
    
    if is_expired(session.created_at):
        raise HTTPException(status_code=403, detail="Session expired")
    
    path = os.path.join("qrs", f"{session_id}.png")
    if not os.path.exists(path):
        raise HTTPException(status_code=404, detail="QR not found")
    return FileResponse(path, media_type="image/png")

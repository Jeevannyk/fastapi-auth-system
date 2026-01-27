from fastapi import FastAPI, HTTPException
from fastapi.responses import FileResponse, RedirectResponse
from fastapi.staticfiles import StaticFiles
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, EmailStr
import sqlite3
import hashlib
import uuid
import qrcode
import os
from datetime import datetime, timedelta
from .database import get_db, init_db


app = FastAPI(title="Antigravity Secure Access")

# -------------------- STATIC FILES --------------------
BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
FRONTEND_DIR = os.path.join(BASE_DIR, "frontend")

app.mount("/static", StaticFiles(directory=FRONTEND_DIR), name="static")

# -------------------- CORS --------------------
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# -------------------- DATABASE --------------------
DB_NAME = "auth.db"

def get_db():
    return sqlite3.connect(DB_NAME)

def init_db():
    db = get_db()
    cur = db.cursor()

    cur.execute("""
        CREATE TABLE IF NOT EXISTS users (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            full_name TEXT NOT NULL,
            email TEXT UNIQUE NOT NULL,
            password TEXT NOT NULL
        )
    """)

    cur.execute("""
        CREATE TABLE IF NOT EXISTS sessions (
            session_id TEXT PRIMARY KEY,
            email TEXT,
            created_at TEXT NOT NULL
        )
    """)

    db.commit()
    db.close()

init_db()

# -------------------- MODELS --------------------
class SignupRequest(BaseModel):
    full_name: str
    email: EmailStr
    access_key: str
    verify_key: str

class LoginRequest(BaseModel):
    email: EmailStr
    access_key: str

class FingerprintRequest(BaseModel):
    email: EmailStr

# -------------------- HELPERS --------------------
def hash_key(key: str) -> str:
    return hashlib.sha256(key.encode()).hexdigest()

def is_expired(created_at: str) -> bool:
    """Check if session has expired (5 minute timeout)"""
    try:
        created = datetime.fromisoformat(created_at)
        return datetime.utcnow() - created > timedelta(minutes=5)
    except:
        return True  # If timestamp is invalid, consider expired

def cleanup_qrs():
    """Delete all QR code files to prevent folder from growing indefinitely"""
    qr_dir = "qrs"
    if os.path.exists(qr_dir):
        for file in os.listdir(qr_dir):
            try:
                os.remove(f"{qr_dir}/{file}")
            except:
                pass  # Ignore errors for files in use

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
def signup(data: SignupRequest):
    if data.access_key != data.verify_key:
        raise HTTPException(status_code=400, detail="Access keys do not match")

    db = get_db()
    cur = db.cursor()

    try:
        cur.execute("""
            INSERT INTO users (full_name, email, password)
            VALUES (?, ?, ?)
        """, (
            data.full_name,
            data.email,
            hash_key(data.access_key)
        ))
        db.commit()
    except sqlite3.IntegrityError:
        raise HTTPException(status_code=400, detail="Email already registered")
    finally:
        db.close()

    return {
        "message": "Access initialized",
        "next": "login"
    }

# ---------- LOGIN ----------
@app.post("/login")
def login(data: LoginRequest):
    db = get_db()
    cur = db.cursor()

    cur.execute(
        "SELECT password FROM users WHERE email=?",
        (data.email,)
    )
    row = cur.fetchone()
    db.close()

    if not row or row[0] != hash_key(data.access_key):
        raise HTTPException(status_code=401, detail="Invalid credentials")

    return {
        "message": "Credentials verified",
        "next": "fingerprint"
    }

# ---------- FINGERPRINT (SIMULATED) ----------
@app.post("/fingerprint")
def fingerprint(data: FingerprintRequest):
    session_id = str(uuid.uuid4())
    created_at = datetime.utcnow().isoformat()

    db = get_db()
    cur = db.cursor()
    
    # Delete any existing sessions for this email to prevent duplicates
    cur.execute("DELETE FROM sessions WHERE email=?", (data.email,))
    
    # Insert new session
    cur.execute(
        "INSERT INTO sessions (session_id, email, created_at) VALUES (?, ?, ?)",
        (session_id, data.email, created_at)
    )
    db.commit()
    db.close()
    
    # Cleanup old QR files periodically (every fingerprint request)
    cleanup_qrs()

    return {
        "message": "Biometric verified",
        "session_id": session_id,
        "next": "qr"
    }

# ---------- QR CODE ----------
@app.get("/qr/{session_id}")
def qr(session_id: str):
    # Validate session exists and hasn't expired
    db = get_db()
    cur = db.cursor()
    cur.execute("SELECT created_at FROM sessions WHERE session_id=?", (session_id,))
    row = cur.fetchone()
    db.close()
    
    if not row:
        raise HTTPException(status_code=404, detail="Session not found")
    
    if is_expired(row[0]):
        raise HTTPException(status_code=403, detail="Session expired")
    
    qr_dir = "qrs"
    os.makedirs(qr_dir, exist_ok=True)

    payload = f"antigravity://connect/{session_id}"
    path = f"{qr_dir}/{session_id}.png"

    img = qrcode.make(payload)
    img.save(path)

    return {
        "qr_image": path,
        "payload": payload
    }

# ---------- SERVE QR IMAGE ----------
@app.get("/qr-image/{session_id}")
def get_qr_image(session_id: str):
    # Validate session exists and hasn't expired
    db = get_db()
    cur = db.cursor()
    cur.execute("SELECT created_at FROM sessions WHERE session_id=?", (session_id,))
    row = cur.fetchone()
    db.close()
    
    if not row:
        raise HTTPException(status_code=404, detail="Session not found")
    
    if is_expired(row[0]):
        raise HTTPException(status_code=403, detail="Session expired")
    
    path = f"qrs/{session_id}.png"
    if not os.path.exists(path):
        raise HTTPException(status_code=404, detail="QR not found")
    return FileResponse(path, media_type="image/png")

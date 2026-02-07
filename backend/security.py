import bcrypt
import pyotp
from jose import jwt, JWTError
from datetime import datetime, timedelta
from fastapi import HTTPException, Header
import os

# Fail fast if SECRET_KEY is not set (allow fallback only in development)
if "SECRET_KEY" not in os.environ:
    if os.getenv("ENVIRONMENT") != "development":
        raise RuntimeError("SECRET_KEY environment variable must be set for production")
    SECRET_KEY = "your-secret-key-change-in-production-use-env-variable"
else:
    SECRET_KEY = os.environ["SECRET_KEY"]

ALGO = "HS256"

def hash_password(password: str) -> str:
    """Hash a password using bcrypt"""
    if not password:
        raise ValueError("Password cannot be empty")
    # Ensure password is a string and encode to bytes
    password_bytes = str(password).encode('utf-8')
    # Hash the password with bcrypt
    salt = bcrypt.gensalt(rounds=12)
    hashed = bcrypt.hashpw(password_bytes, salt)
    return hashed.decode('utf-8')

def verify_password(password: str, hashed_password: str) -> bool:
    """Verify a password against a hashed password"""
    if not password or not hashed_password:
        return False
    try:
        password_bytes = str(password).encode('utf-8')
        hashed_bytes = hashed_password.encode('utf-8')
        return bcrypt.checkpw(password_bytes, hashed_bytes)
    except Exception:
        return False

def create_token(user_id):
    payload = {
        "sub": str(user_id),
        "exp": datetime.utcnow() + timedelta(minutes=30)
    }
    return jwt.encode(payload, SECRET_KEY, algorithm=ALGO)

def verify_otp(secret, otp):
    return pyotp.TOTP(secret).verify(otp)

def verify_token(authorization: str = Header(None)):
    """Verify JWT token from Authorization header"""
    if not authorization:
        raise HTTPException(status_code=401, detail="Authorization header missing")
    
    try:
        # Extract token from "Bearer <token>" format
        if not authorization.startswith("Bearer "):
            raise HTTPException(status_code=401, detail="Invalid authorization format")
        
        token = authorization.split(" ")[1]
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGO])
        
        # Get user info from token
        user_id = payload.get("sub")
        if not user_id:
            raise HTTPException(status_code=401, detail="Invalid token payload")
        
        # Return user info (only what's actually in the token)
        return {"user_id": user_id}
    
    except JWTError:
        raise HTTPException(status_code=401, detail="Invalid or expired token")
    except IndexError:
        raise HTTPException(status_code=401, detail="Invalid authorization format")

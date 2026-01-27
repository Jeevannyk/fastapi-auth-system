from passlib.context import CryptContext
import pyotp
from jose import jwt
from datetime import datetime, timedelta

pwd = CryptContext(schemes=["bcrypt"], deprecated="auto")

SECRET_KEY = "secret"
ALGO = "HS256"

def hash_password(password: str) -> str:
    """Hash a password using bcrypt"""
    if not password:
        raise ValueError("Password cannot be empty")
    # Ensure password is a string and encode properly
    return pwd.hash(str(password))

def verify_password(password: str, hashed_password: str) -> bool:
    """Verify a password against a hashed password"""
    if not password or not hashed_password:
        return False
    return pwd.verify(str(password), hashed_password)

def create_token(user_id):
    payload = {
        "sub": str(user_id),
        "exp": datetime.utcnow() + timedelta(minutes=30)
    }
    return jwt.encode(payload, SECRET_KEY, algorithm=ALGO)

def verify_otp(secret, otp):
    return pyotp.TOTP(secret).verify(otp)

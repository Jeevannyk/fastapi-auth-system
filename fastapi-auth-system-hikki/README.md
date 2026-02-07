# CyberGuard Secure Access System 🔐

A **production-grade authentication system** built with FastAPI featuring Google OAuth 2.0, WebAuthn/Passkeys for biometric authentication, and real MFA with email verification.

## ✨ Features

### 🔑 Multi-Factor Authentication (Google-Style)
- **Real MFA Verification**: Number matching challenge sent via email
- **Time-Limited Codes**: 2-minute expiry with single-use enforcement
- **Attempt Limiting**: Maximum 3 attempts per challenge
- **Secure Code Generation**: Cryptographically secure random numbers

### 🌐 Google OAuth 2.0
- **Sign in with Google**: One-click authentication with verified Gmail
- **Auto Account Creation**: New users automatically registered
- **Account Linking**: Existing users can link Google accounts

### 👆 WebAuthn / Passkeys (Biometric Authentication)
- **Windows Hello**: Fingerprint, face, or PIN
- **Apple Touch ID / Face ID**: Native biometric support
- **Android Biometrics**: Fingerprint scanner support
- **FIDO2 Security Keys**: Hardware key support

### 🔒 Security Features
- **No Biometric Data Stored**: Public-key cryptography only
- **No System Passwords Used**: Independent authentication
- **256-bit Encryption**: Industry-standard security
- **JWT Tokens**: Stateless session management
- **CORS Protection**: Environment-based origin control

## 🛠️ Tech Stack

**Backend**
- FastAPI 0.127.0 - High-performance async web framework
- SQLAlchemy 2.0.36 - SQL toolkit and ORM
- Bcrypt 5.0.0 - Password hashing
- Python-jose 3.5.0 - JWT token management
- httpx 0.27.0 - Async HTTP client (Google OAuth)
- aiosmtplib 3.0.1 - Async email sending (MFA)

**Frontend**
- HTML5, CSS3, Vanilla JavaScript
- TailwindCSS 3.x - Utility-first CSS
- WebAuthn API - Native biometric support
- Material Icons - Icon library

## 📁 Project Structure

```
cyberguard-auth/
├── backend/
│   ├── __init__.py
│   ├── main.py          # FastAPI app & all routes
│   ├── models.py        # User, WebAuthn, MFA models
│   ├── database.py      # Database config
│   └── security.py      # Crypto, JWT, MFA, WebAuthn helpers
├── frontend/
│   ├── login.html       # Login page with Google + WebAuthn
│   ├── login.js         # Complete auth logic
│   ├── signup.html      # Registration page
│   ├── signup.js        # Signup logic
│   ├── home.html        # Dashboard
│   ├── home.js          # Dashboard logic
│   └── fingerprint.js   # WebAuthn module
├── .env                 # Environment configuration
├── .env.example         # Configuration template
├── auth.db              # SQLite database
├── requirements.txt     # Python dependencies
├── start.bat            # Windows startup script
└── start.sh             # Unix startup script
```

## 🚀 Quick Start

### Windows (PowerShell)
```powershell
cd fastapi-auth-system-hikki
$env:ENVIRONMENT="development"
$env:SECRET_KEY="your-secret-key-here"
pip install -r requirements.txt
python -m uvicorn backend.main:app --host 127.0.0.1 --port 8000 --reload
```

### macOS/Linux
```bash
cd fastapi-auth-system-hikki
export ENVIRONMENT=development
export SECRET_KEY=your-secret-key-here
pip install -r requirements.txt
uvicorn backend.main:app --host 127.0.0.1 --port 8000 --reload
```

### Access Points
- **Login Page**: http://127.0.0.1:8000/login
- **API Documentation**: http://127.0.0.1:8000/docs
- **Health Check**: http://127.0.0.1:8000/health

## ⚙️ Configuration

Edit `.env` file to configure:

### Required Settings
```env
SECRET_KEY=your-super-secret-key-change-in-production
ENVIRONMENT=development
```

### Google OAuth 2.0 (Optional)
```env
GOOGLE_CLIENT_ID=your-client-id.apps.googleusercontent.com
GOOGLE_CLIENT_SECRET=your-client-secret
GOOGLE_REDIRECT_URI=http://localhost:8000/auth/google/callback
```

**Setup Steps:**
1. Go to [Google Cloud Console](https://console.cloud.google.com/)
2. Create a project → Credentials → OAuth 2.0 Client ID
3. Set redirect URI: `http://localhost:8000/auth/google/callback`
4. Copy Client ID and Secret to `.env`

### Email MFA (Optional)
```env
SMTP_HOST=smtp.gmail.com
SMTP_PORT=587
SMTP_USER=your-email@gmail.com
SMTP_PASSWORD=your-app-password
SMTP_FROM_EMAIL=noreply@cyberguard.com
```

**For Gmail:** Use [App Passwords](https://myaccount.google.com/apppasswords)

### WebAuthn Settings
```env
WEBAUTHN_RP_ID=localhost
WEBAUTHN_RP_NAME=CyberGuard Secure Access
WEBAUTHN_ORIGIN=http://localhost:8000
```

> **Note:** For production, set `WEBAUTHN_RP_ID` to your actual domain.

## 🔐 Authentication Flow

### 1. Password Login + MFA
```
User enters email/password
      ↓
Backend verifies credentials
      ↓
Partial token issued (5-min expiry)
      ↓
MFA challenge generated (2-digit code)
      ↓
Code sent via email + shown on screen
      ↓
User selects matching number
      ↓
Full access token issued
      ↓
(Optional) WebAuthn registration offered
```

### 2. Google Sign-In
```
User clicks "Sign in with Google"
      ↓
Redirect to Google OAuth consent
      ↓
User authenticates with Google
      ↓
Callback with authorization code
      ↓
Backend exchanges for access token
      ↓
User info fetched from Google
      ↓
User created/updated in database
      ↓
Full access token issued (MFA bypassed)
```

### 3. WebAuthn (Fingerprint) Login
```
User enters email
      ↓
Clicks "Sign in with Fingerprint"
      ↓
Browser prompts for biometric
      ↓
WebAuthn assertion generated
      ↓
Backend verifies credential
      ↓
Full access token issued (MFA bypassed)
```

## 📡 API Endpoints

### Authentication
| Method | Endpoint | Description |
|--------|----------|-------------|
| POST | `/signup` | Register new user |
| POST | `/login` | Password login (returns partial token) |
| POST | `/mfa/generate` | Generate MFA challenge |
| POST | `/mfa/verify` | Verify MFA code |

### Google OAuth
| Method | Endpoint | Description |
|--------|----------|-------------|
| GET | `/auth/google` | Initiate Google OAuth |
| GET | `/auth/google/callback` | OAuth callback |
| GET | `/auth/google/status` | Check OAuth configuration |

### WebAuthn / Passkeys
| Method | Endpoint | Description |
|--------|----------|-------------|
| POST | `/webauthn/register/options` | Get registration challenge |
| POST | `/webauthn/register/complete` | Complete registration |
| POST | `/webauthn/authenticate/options` | Get auth challenge |
| POST | `/webauthn/authenticate/complete` | Complete authentication |
| GET | `/webauthn/credentials/{email}` | Check user credentials |

## 🧪 Testing

### Create Test User
```python
from backend.database import SessionLocal
from backend.models import User
from backend.security import hash_password

db = SessionLocal()
user = User(
    full_name="Test User",
    email="test@example.com",
    password_hash=hash_password("password123")
)
db.add(user)
db.commit()
```

### Test Login
```bash
curl -X POST http://127.0.0.1:8000/login \
  -H "Content-Type: application/json" \
  -d '{"email": "test@example.com", "access_key": "password123"}'
```

## 🔒 Security Notes

1. **Change SECRET_KEY** in production
2. **Use HTTPS** in production (required for WebAuthn)
3. **Configure allowed origins** in ALLOWED_ORIGINS
4. **Set ENVIRONMENT=production** for production
5. **Use proper SMTP credentials** for email MFA

## 📄 License

MIT License - Feel free to use in your projects.

---

Built with ❤️ using FastAPI, WebAuthn, and Google OAuth 2.0

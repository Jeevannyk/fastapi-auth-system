# FastAPI Authentication System 🚀

A modern, secure authentication system built with FastAPI, featuring multi-step authentication flow with biometric verification and QR code generation.

## ✨ Features

- **Multi-Step Authentication Flow**: Email/Password → Biometric Fingerprint → QR Code → Home Dashboard
- **Secure Password Hashing**: Industry-standard bcrypt with 12-round salt
- **JWT Token Authentication**: Stateless session management with 30-minute expiry
- **SQLAlchemy ORM**: Type-safe database operations with declarative models
- **Modern UI**: Responsive cybersecurity-themed interface with TailwindCSS
- **Path Traversal Protection**: UUID validation preventing malicious session access
- **Timezone-aware Sessions**: UTC datetime handling for global consistency
- **CORS Configuration**: Environment-based security settings

## 🛠️ Tech Stack

**Backend**
- FastAPI 0.127.0 - High-performance async web framework
- SQLAlchemy 2.0.46 - SQL toolkit and ORM
- Bcrypt 5.0.0 - Password hashing
- Python-jose 3.5.0 + PyJWT 2.10.1 - JWT token management
- QRCode 8.2 - QR code generation

**Frontend**
- HTML5, CSS3, Vanilla JavaScript
- TailwindCSS 3.x - Utility-first CSS
- Material Icons - Icon library

**Database**
- SQLite (development)
- Production-ready for PostgreSQL/MySQL

## 📁 Project Structure

```
fastapi-auth-system/
├── backend/
│   ├── __init__.py
│   ├── main.py          # FastAPI app & routes
│   ├── models.py        # SQLAlchemy User & Session models
│   ├── database.py      # Database config & connection
│   └── security.py      # Password hashing & JWT tokens
├── frontend/
│   ├── login.html       # Login page
│   ├── login.js         # Login logic
│   ├── signup.html      # Registration page
│   ├── signup.js        # Signup logic
│   ├── home.html        # Dashboard
│   ├── home.js          # Dashboard logic
│   ├── fingerprint.js   # Biometric verification
├── qrs/                 # Generated QR code images
├── auth.db              # SQLite database
├── init_db.py           # Database initialization script
├── check_db.py          # Database inspection utility
├── test_complete.py     # End-to-end test suite
├── requirements.txt     # Python dependencies
├── .env.example         # Environment variables template
├── start.bat            # Windows startup script
└── start.sh             # Unix startup script

```

## 🚀 Quick Start

### Prerequisites
- Python 3.8 or higher
- pip (Python package installer)

### Installation

1. **Clone the repository**
```bash
git clone <repository-url>
cd fastapi-auth-system
```

2. **Create virtual environment (recommended)**
```bash
python -m venv .venv

# Windows
.venv\Scripts\activate

# macOS/Linux
source .venv/bin/activate
```

3. **Install dependencies**
```bash
pip install -r requirements.txt
```

4. **Set up environment variables** (optional)
```bash
# Windows
copy .env.example .env

# macOS/Linux
cp .env.example .env

# Edit .env and set a secure SECRET_KEY (random 32+ character string)
```

5. **Initialize the database**
```bash
python init_db.py
```

This creates `auth.db` with a test user:
- **Email**: test@example.com
- **Access Key**: password123

## 🏃 Running the Application

### Option 1: Direct Command
```bash
uvicorn backend.main:app --host 127.0.0.1 --port 8000
```

### Option 2: With Auto-reload (Development)
```bash
uvicorn backend.main:app --host 127.0.0.1 --port 8000 --reload
```

### Option 3: Using Startup Scripts

**Windows:**
```bash
start.bat
```

**macOS/Linux:**
```bash
chmod +x start.sh
./start.sh
```

The application will be available at:
- **Frontend**: http://127.0.0.1:8000/
- **API Docs**: http://127.0.0.1:8000/docs
- **Health Check**: http://127.0.0.1:8000/health

## 📖 API Documentation

### Authentication Flow

The system implements a 3-step authentication process:

#### Step 1: Login (Credentials)
**POST** `/login`

```json
Request:
{
  "email": "test@example.com",
  "access_key": "password123"
}

Response:
{
  "message": "Credentials verified",
  "access_token": "eyJhbGc...",
  "next": "fingerprint"
}
```

#### Step 2: Biometric Verification
**POST** `/fingerprint`

```json
Request:
{
  "email": "test@example.com"
}

Response:
{
  "message": "Biometric verified",
  "session_id": "550e8400-e29b-41d4-a716-446655440000",
  "next": "qr"
}
```

#### Step 3: QR Code Generation
**GET** `/qr/{session_id}`

```json
Response:
{
  "qr_image": "qrs/550e8400-e29b-41d4-a716-446655440000.png",
  "payload": "antigravity://connect/550e8400-e29b-41d4-a716-446655440000"
}
```

**GET** `/qr-image/{session_id}`
- Returns QR code image as PNG
- Content-Type: `image/png`

### Other Endpoints

**GET** `/health`
```json
{
  "status": "ok"
}
```

**POST** `/signup`
```json
Request:
{
  "full_name": "John Doe",
  "email": "john@example.com",
  "access_key": "securepassword123"
}

Response:
{
  "message": "User registered successfully",
  "email": "john@example.com"
}
```

## 🧪 Testing

### Run Complete Test Suite
```bash
# Make sure server is running first
python test_complete.py
```

Tests include:
- ✅ Health check
- ✅ Frontend page loading
- ✅ User signup
- ✅ User login & JWT tokens
- ✅ Invalid credentials rejection
- ✅ Fingerprint/session creation
- ✅ QR code generation
- ✅ QR image serving
- ✅ Path traversal protection

### Individual Test Scripts
```bash
python test_database.py    # Database connectivity
python test_signup.py      # Signup endpoint
python test_login.py       # Login endpoint
```

### Database Utilities
```bash
python check_db.py         # View all users and sessions
python init_db.py          # Reset database with test user
```

## 🔒 Security Features

1. **Password Security**
   - Bcrypt hashing with 12-round salt
   - 72-byte password limit (bcrypt standard)
   - Never stores plaintext passwords

2. **JWT Tokens**
   - HS256 algorithm
   - 30-minute expiry
   - Stored in localStorage (frontend)

3. **Session Management**
   - UUID-based session IDs
   - Timezone-aware timestamps
   - Path traversal validation

4. **Input Validation**
   - Pydantic models for request validation
   - Email format validation
   - UUID format validation
   - SQL injection protection via ORM

5. **CORS Configuration**
   - Environment-based allowed origins
   - Credentials support
   - Configurable methods and headers

## 🗄️ Database Schema

### Users Table
```sql
id           INTEGER PRIMARY KEY AUTOINCREMENT
full_name    VARCHAR NOT NULL
email        VARCHAR UNIQUE NOT NULL
password_hash VARCHAR NOT NULL
created_at   DATETIME DEFAULT CURRENT_TIMESTAMP
```

### Sessions Table
```sql
session_id   VARCHAR(36) PRIMARY KEY  -- UUID format
email        VARCHAR NOT NULL
created_at   DATETIME DEFAULT CURRENT_TIMESTAMP
```

## 🛠️ Troubleshooting

### Port Already in Use
```bash
# Windows - Kill process on port 8000
netstat -ano | findstr :8000
taskkill /PID <PID> /F

# macOS/Linux
lsof -ti:8000 | xargs kill -9
```

### Database Locked Error
```bash
# Close all connections and reinitialize
python init_db.py
```

### Module Not Found Error
```bash
# Ensure virtual environment is activated
pip install -r requirements.txt
```

## 📝 Environment Variables

Create `.env` file based on `.env.example`:

```env
SECRET_KEY=your-secret-key-here-minimum-32-characters
DATABASE_URL=sqlite:///./auth.db
ALLOWED_ORIGINS=http://localhost:8000,http://127.0.0.1:8000
TOKEN_EXPIRE_MINUTES=30
```

## 🤝 Contributing

1. Fork the repository
2. Create a feature branch (`git checkout -b feature/amazing-feature`)
3. Commit your changes (`git commit -m 'Add amazing feature'`)
4. Push to the branch (`git push origin feature/amazing-feature`)
5. Open a Pull Request

## 📄 License

This project is licensed under the MIT License.

## 🙏 Acknowledgments

- FastAPI for the excellent web framework
- SQLAlchemy for robust ORM
- TailwindCSS for beautiful styling

---

**Built with ❤️ using FastAPI**

Access at:
- **Frontend**: http://127.0.0.1:8000
- **API Docs**: http://127.0.0.1:8000/docs

## 🔒 Authentication Flow

1. **Signup** → POST `/signup` - Create account
2. **Login** → POST `/login` - Get JWT token
3. **Fingerprint** → POST `/fingerprint` - Biometric verification (simulated)
4. **QR Code** → GET `/qr-image/{session_id}` - Device pairing
5. **Dashboard** → `/home` - Authenticated access

## 🗄️ Database Models

### User
- `id`, `full_name`, `email` (unique), `password_hash`, `created_at`

### Session
- `session_id` (UUID), `email`, `created_at` (expires in 5 minutes)

## 🛠️ Utility Scripts

```bash
python check_db.py        # List all users
python add_user.py         # Add test user
python test_signup.py      # Test signup endpoint
python test_login.py       # Test login endpoint
python test_database.py    # Database connection test
```

## 🐛 Fixed Issues

✅ Database consistency (auth.db across all modules)
✅ Proper User model with SQLAlchemy
✅ Bcrypt password hashing (not SHA256)
✅ JWT token authentication
✅ Timezone-aware datetime
✅ Path traversal protection
✅ CORS security configuration
✅ Frontend token storage
✅ HTML encoding fixes
✅ All API endpoint mismatches

## 📂 Project Structure
fastapi-auth-system/
FASTAPI/
│
├── backend/
│   ├── __init__.py
│   ├── main.py
│   ├── database.py
│   ├── models.py
│   └── security.py
│
├── frontend/
│   ├── home.html
│   ├── home.js
│   ├── login.html
│   ├── login.js
│   ├── signup.html
│   ├── signup.js
│   └── fingerprint.js
│
├── tests/
│   ├── test_login.py
│   ├── test_signup.py
│   └── test_database.py
│
├── .gitignore
├── README.md
├── requirements.txt
└── DATABASE_STATUS.md

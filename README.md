# FastAPI Authentication System 🚀

A secure authentication system built using FastAPI, designed to demonstrate backend development, authentication logic, and clean API practices.

## 🔐 Features
- User signup & login
- Password hashing
- Backend validation
- Modular FastAPI structure
- Easy to extend with JWT / OTP / MFA

## 🛠 Tech Stack
- Backend: FastAPI
- Language: Python
- Database: SQLite
- ORM: SQLAlchemy
- Frontend: HTML, CSS, JavaScript

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

"""Create a test user in the database"""
from backend.database import SessionLocal
from backend.models import User
from backend.security import hash_password

db = SessionLocal()

# Create test user
test_user = User(
    username="testuser",
    email="test@example.com",
    password=hash_password("password123"),
    mfa_enabled=False
)

db.add(test_user)
db.commit()
db.refresh(test_user)

print("\n✅ Test user created successfully!")
print("\nLogin credentials:")
print("  Username: testuser")
print("  Password: password123")
print("\nYou can now login at: http://127.0.0.1:8000\n")

db.close()

"""Initialize database with fresh schema and test user"""
import os
from backend.database import SessionLocal, Base, engine
from backend.models import User
from backend.security import hash_password

# Delete old database if exists
db_path = "test_v2.db"
if os.path.exists(db_path):
    os.remove(db_path)
    print(f"✅ Removed old database: {db_path}")

# Create all tables with new schema
print("📊 Creating database tables...")
Base.metadata.create_all(bind=engine)
print("✅ Database tables created successfully!")

# Create test user
print("\n👤 Creating test user...")
db = SessionLocal()

try:
    test_user = User(
        username="testuser",
        email="test@example.com",
        password=hash_password("password123"),
        mfa_enabled=False
    )
    
    db.add(test_user)
    db.commit()
    db.refresh(test_user)
    
    print("✅ Test user created successfully!")
    print("\n" + "="*50)
    print("LOGIN CREDENTIALS")
    print("="*50)
    print(f"  URL:      http://127.0.0.1:8000")
    print(f"  Username: testuser")
    print(f"  Password: password123")
    print("="*50)
    
except Exception as e:
    print(f"❌ Error: {e}")
    db.rollback()
finally:
    db.close()

print("\n✅ Database initialization complete!\n")

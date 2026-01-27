"""Initialize database with fresh schema and test user"""
import os
import sys
from backend.database import SessionLocal, engine
from backend.models import Base, User
from backend.security import hash_password

# Delete old database if exists (with confirmation)
db_path = "auth.db"
if os.path.exists(db_path):
    # Check if running in production (prevent accidental deletion)
    if os.getenv("ENVIRONMENT") == "production":
        print("❌ Cannot delete database in production environment")
        sys.exit(1)
    
    # Require confirmation for database deletion
    print(f"⚠️  WARNING: This will delete the existing database: {db_path}")
    confirmation = input("Type 'DELETE' to confirm: ").strip()
    
    if confirmation != "DELETE":
        print("❌ Database deletion cancelled")
        sys.exit(0)
    
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
        full_name="Test User",
        email="test@example.com",
        password_hash=hash_password("password123")
    )
    
    db.add(test_user)
    db.commit()
    db.refresh(test_user)
    
    print("✅ Test user created successfully!")
    print("\n" + "="*50)
    print("LOGIN CREDENTIALS")
    print("="*50)
    print(f"  URL:      http://127.0.0.1:8000")
    print(f"  Email:    test@example.com")
    print(f"  Password: password123")
    print("="*50)
    
except Exception as e:
    print(f"❌ Error: {e}")
    db.rollback()
finally:
    db.close()

print("\n✅ Database initialization complete!\n")

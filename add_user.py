"""Add test user to existing database"""
from backend.database import SessionLocal, Base, engine
from backend.models import User
from backend.security import hash_password

# Ensure tables exist (won't recreate if they already exist)
print("📊 Checking database tables...")
Base.metadata.create_all(bind=engine)
print("✅ Database tables verified!")

# Create test user
print("\n👤 Creating test user...")
db = SessionLocal()

try:
    # Check if user already exists
    existing = db.query(User).filter(User.username == "testuser").first()
    
    if existing:
        print("⚠️  Test user already exists!")
        print(f"   Username: {existing.username}")
        print(f"   Email: {existing.email}")
    else:
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
    
    # Show all users
    all_users = db.query(User).all()
    print(f"\n📋 Total users in database: {len(all_users)}")
    for user in all_users:
        print(f"   - {user.username} ({user.email})")
    
except Exception as e:
    print(f"❌ Error: {e}")
    import traceback
    traceback.print_exc()
    db.rollback()
finally:
    db.close()

print("\n✅ Complete!\n")

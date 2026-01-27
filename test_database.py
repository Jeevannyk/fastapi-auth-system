"""
Database Connection Test & User Management Script
This script verifies the database connection and allows you to:
1. Check existing users
2. Create a test user
3. Verify database structure
"""

from backend.database import SessionLocal, engine, Base
from backend.models import User
from backend.security import hash_password

def check_database():
    """Check if database tables exist and display structure"""
    print("=" * 60)
    print("DATABASE CONNECTION TEST")
    print("=" * 60)
    
    # Create tables if they don't exist
    print("\n📊 Creating/Verifying database tables...")
    Base.metadata.create_all(bind=engine)
    print("✅ Database tables created/verified successfully!")
    
    # Get table info
    print(f"\n📋 Database URL: sqlite:///./test_v2.db")
    print(f"📋 Tables: {list(Base.metadata.tables.keys())}")
    
    return True

def list_users():
    """List all users in the database"""
    db = SessionLocal()
    try:
        users = db.query(User).all()
        print(f"\n👥 Total Users in Database: {len(users)}")
        print("-" * 60)
        
        if users:
            for user in users:
                print(f"ID: {user.id}")
                print(f"Username: {user.username}")
                print(f"Email: {user.email}")
                print(f"MFA Enabled: {user.mfa_enabled}")
                print("-" * 60)
        else:
            print("⚠️  No users found in database!")
            
        return users
    finally:
        db.close()

def create_test_user():
    """Create a test user for testing the application"""
    db = SessionLocal()
    try:
        # Check if test user already exists
        existing = db.query(User).filter(
            (User.username == "testuser") | (User.email == "test@example.com")
        ).first()
        
        if existing:
            print("\n⚠️  Test user already exists!")
            return existing
        
        # Create new test user
        test_user = User(
            username="testuser",
            email="test@example.com",
            password=hash_password("password123"),
            mfa_enabled=False
        )
        
        db.add(test_user)
        db.commit()
        db.refresh(test_user)
        
        print("\n✨ Test User Created Successfully!")
        print(f"   Username: testuser")
        print(f"   Password: password123")
        print(f"   Email: test@example.com")
        
        return test_user
    except Exception as e:
        print(f"\n❌ Error creating test user: {e}")
        db.rollback()
        return None
    finally:
        db.close()

def main():
    """Main function to run database tests"""
    print("\n🚀 Starting Database Connection Test...\n")
    
    # Check database connection
    if check_database():
        print("\n✅ Database connection successful!")
    
    # List existing users
    users = list_users()
    
    # Offer to create test user if none exist
    if len(users) == 0:
        print("\n💡 Would you like to create a test user?")
        response = input("Create test user? (y/n): ").lower().strip()
        if response == 'y':
            create_test_user()
            print("\n📋 Updated user list:")
            list_users()
    
    print("\n" + "=" * 60)
    print("✅ DATABASE TEST COMPLETE!")
    print("=" * 60)
    print("\n💡 You can now:")
    print("   1. Go to http://127.0.0.1:8000")
    print("   2. Login with username: testuser")
    print("   3. Password: password123")
    print("=" * 60 + "\n")

if __name__ == "__main__":
    main()

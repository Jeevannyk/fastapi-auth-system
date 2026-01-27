"""Quick database check script"""
from backend.database import SessionLocal, Base, engine
from backend.models import User

# Ensure tables exist
Base.metadata.create_all(bind=engine)

# Check users
db = SessionLocal()
users = db.query(User).all()

print(f"\nTotal users in database: {len(users)}\n")

if users:
    for user in users:
        print(f"  - Username: {user.username}")
        print(f"    Email: {user.email}")
        print(f"    ID: {user.id}")
        print()
else:
    print("  No users found!\n")

db.close()

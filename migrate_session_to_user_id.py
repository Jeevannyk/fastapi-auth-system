"""
Migration script: Convert Session.email FK to Session.user_id FK

This script migrates the sessions table from using email as a foreign key
to using user_id (integer) for better referential integrity.
"""
import sqlite3
import sys

def migrate_database():
    """Migrate sessions table from email FK to user_id FK"""
    db_path = "auth.db"
    
    try:
        # Use context manager for automatic connection handling
        with sqlite3.connect(db_path) as conn:
            cursor = conn.cursor()
            
            print("🔄 Starting migration: Session.email → Session.user_id")
            
            # Check if migration is needed
            cursor.execute("PRAGMA table_info(sessions)")
            columns = {col[1]: col for col in cursor.fetchall()}
            
            if "user_id" in columns:
                print("✅ Migration already applied (user_id column exists)")
                return
            
            if "email" not in columns:
                print("❌ Unexpected schema: sessions table missing email column")
                sys.exit(1)
            
            # Check for orphaned sessions (sessions with no matching user)
            print("🔍 Checking for orphaned sessions...")
            cursor.execute("""
                SELECT COUNT(*) 
                FROM sessions s 
                LEFT JOIN users u ON s.email = u.email 
                WHERE u.id IS NULL
            """)
            orphaned_count = cursor.fetchone()[0]
            
            if orphaned_count > 0:
                print(f"⚠️  WARNING: Found {orphaned_count} orphaned session(s) with no matching user")
                print("   These sessions will be DROPPED during migration.")
                response = input("   Continue anyway? (yes/no): ").strip().lower()
                
                if response != "yes":
                    print("❌ Migration aborted")
                    sys.exit(0)
            else:
                print("✅ No orphaned sessions found")
            
            # Step 1: Create new sessions table with user_id
            print("📊 Creating new sessions table with user_id...")
            cursor.execute("""
                CREATE TABLE sessions_new (
                    session_id TEXT PRIMARY KEY,
                    user_id INTEGER NOT NULL,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    expires_at TIMESTAMP,
                    FOREIGN KEY (user_id) REFERENCES users (id)
                )
            """)
            
            # Step 2: Copy data from old table, mapping email to user_id
            print("📋 Migrating existing session data...")
            cursor.execute("""
                INSERT INTO sessions_new (session_id, user_id, created_at, expires_at)
                SELECT 
                    s.session_id,
                    u.id,
                    s.created_at,
                    s.expires_at
                FROM sessions s
                INNER JOIN users u ON s.email = u.email
            """)
            
            migrated_count = cursor.rowcount
            print(f"✅ Migrated {migrated_count} session(s)")
            
            # Step 3: Drop old table and rename new table
            print("🔄 Replacing old sessions table...")
            cursor.execute("DROP TABLE sessions")
            cursor.execute("ALTER TABLE sessions_new RENAME TO sessions")
            
            # Step 4: Create index on user_id for performance
            print("📌 Creating index on user_id...")
            cursor.execute("CREATE INDEX idx_sessions_user_id ON sessions(user_id)")
            
            # Commit changes (context manager auto-commits on success)
            conn.commit()
            print("✅ Migration completed successfully!")
            
            # Verify migration
            cursor.execute("SELECT COUNT(*) FROM sessions")
            final_count = cursor.fetchone()[0]
            print(f"📊 Final session count: {final_count}")
        
    except sqlite3.Error as e:
        print(f"❌ Database error: {e}")
        print("   Transaction has been rolled back automatically")
        sys.exit(1)
    except Exception as e:
        print(f"❌ Migration failed: {e}")
        print("   Transaction has been rolled back automatically")
        sys.exit(1)

if __name__ == "__main__":
    print("="*60)
    print("  Session Table Migration: email → user_id")
    print("="*60)
    print()
    
    response = input("This will modify the sessions table. Continue? (yes/no): ").strip().lower()
    
    if response == "yes":
        migrate_database()
    else:
        print("❌ Migration cancelled")
        sys.exit(0)

#!/usr/bin/env python3
"""
Database reset script for Enterprise RAG System
Drops all tables, runs migrations, and seeds initial data
"""

import os
import sys
import subprocess
import time

# Add the src directory to the path
sys.path.append(os.path.join(os.path.dirname(__file__), '..', 'src'))

from sqlalchemy import create_engine, text
from sqlalchemy.orm import sessionmaker

# Database configuration
DATABASE_URL = os.getenv("DATABASE_URL", "postgresql://admin:password@postgres:5432/rag_searcher")

def wait_for_database():
    """Wait for database to be available"""
    print("⏳ Waiting for database connection...")
    max_attempts = 30
    attempt = 0
    
    while attempt < max_attempts:
        try:
            engine = create_engine(DATABASE_URL)
            with engine.connect() as conn:
                conn.execute(text("SELECT 1"))
            print("✅ Database connection successful")
            return True
        except Exception as e:
            attempt += 1
            print(f"  Attempt {attempt}/{max_attempts}: {e}")
            time.sleep(2)
    
    print("❌ Failed to connect to database")
    return False

def drop_all_tables():
    """Drop all tables in the database"""
    print("🗑️ Dropping all tables...")
    
    try:
        engine = create_engine(DATABASE_URL)
        with engine.connect() as conn:
            # Get all table names
            result = conn.execute(text("""
                SELECT tablename FROM pg_tables 
                WHERE schemaname = 'public' 
                AND tablename != 'alembic_version'
            """))
            tables = [row[0] for row in result.fetchall()]
            
            if tables:
                # Drop all tables with CASCADE
                tables_str = ', '.join(tables)
                conn.execute(text(f"DROP TABLE IF EXISTS {tables_str} CASCADE"))
                conn.commit()
                print(f"  ✅ Dropped {len(tables)} tables")
            else:
                print("  ⏭️ No tables to drop")
                
            # Also drop alembic_version to start fresh
            conn.execute(text("DROP TABLE IF EXISTS alembic_version CASCADE"))
            conn.commit()
            print("  ✅ Dropped alembic_version table")
            
    except Exception as e:
        print(f"❌ Error dropping tables: {e}")
        raise

def run_migrations():
    """Run Alembic migrations"""
    print("🔄 Running Alembic migrations...")
    
    try:
        # Change to the core-api directory
        os.chdir('/app')
        
        # Run alembic upgrade
        result = subprocess.run(
            ['alembic', 'upgrade', 'head'],
            capture_output=True,
            text=True,
            check=True
        )
        
        print("  ✅ Migrations completed successfully")
        if result.stdout:
            print(f"  Output: {result.stdout}")
            
    except subprocess.CalledProcessError as e:
        print(f"❌ Migration failed: {e}")
        if e.stdout:
            print(f"  Stdout: {e.stdout}")
        if e.stderr:
            print(f"  Stderr: {e.stderr}")
        raise
    except Exception as e:
        print(f"❌ Error running migrations: {e}")
        raise

def seed_database():
    """Run database seeding"""
    print("🌱 Seeding database...")
    
    try:
        # Import and run the seeding script
        from seed_database import main as seed_main
        seed_main()
        print("  ✅ Database seeding completed")
        
    except Exception as e:
        print(f"❌ Error seeding database: {e}")
        raise

def verify_setup():
    """Verify the database setup is correct"""
    print("🔍 Verifying database setup...")
    
    try:
        engine = create_engine(DATABASE_URL)
        SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
        db = SessionLocal()
        
        # Check tables exist
        tables_to_check = [
            'users', 'roles', 'permissions', 'user_roles', 'role_permissions',
            'organizations', 'organization_members', 'organization_domains',
            'files', 'embeddings', 'chat_sessions', 'chat_messages'
        ]
        
        for table in tables_to_check:
            result = db.execute(text(f"SELECT COUNT(*) FROM {table}"))
            count = result.scalar()
            print(f"  ✅ {table}: {count} records")
        
        # Check specific data
        roles_count = db.execute(text("SELECT COUNT(*) FROM roles")).scalar()
        perms_count = db.execute(text("SELECT COUNT(*) FROM permissions")).scalar()
        mappings_count = db.execute(text("SELECT COUNT(*) FROM role_permissions")).scalar()
        
        print(f"\n📊 Summary:")
        print(f"  Roles: {roles_count}")
        print(f"  Permissions: {perms_count}")
        print(f"  Role-Permission mappings: {mappings_count}")
        
        if roles_count >= 4 and perms_count >= 15 and mappings_count >= 10:
            print("  ✅ Database setup looks good!")
            return True
        else:
            print("  ⚠️ Database setup may be incomplete")
            return False
            
    except Exception as e:
        print(f"❌ Error verifying setup: {e}")
        return False
    finally:
        db.close()

def main():
    """Main reset function"""
    print("🔄 Starting database reset...")
    print("=" * 50)
    
    try:
        # Step 1: Wait for database
        if not wait_for_database():
            return False
        
        # Step 2: Drop all tables
        drop_all_tables()
        
        # Step 3: Run migrations
        run_migrations()
        
        # Step 4: Seed database
        seed_database()
        
        # Step 5: Verify setup
        if verify_setup():
            print("\n🎉 Database reset completed successfully!")
            print("=" * 50)
            return True
        else:
            print("\n❌ Database reset completed but verification failed")
            return False
            
    except Exception as e:
        print(f"\n❌ Database reset failed: {e}")
        return False

if __name__ == "__main__":
    success = main()
    sys.exit(0 if success else 1) 
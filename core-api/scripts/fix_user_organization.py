#!/usr/bin/env python3
"""
Fix user organization membership for file upload
"""

import os
import sys
import uuid
from datetime import datetime

# Add the src directory to the path
sys.path.append(os.path.join(os.path.dirname(__file__), '..', 'src'))

from sqlalchemy import create_engine, text
from sqlalchemy.orm import sessionmaker

# Database configuration
DATABASE_URL = os.getenv("DATABASE_URL", "postgresql://admin:password@postgres:5432/rag_searcher")

def create_db_session():
    """Create database session"""
    engine = create_engine(DATABASE_URL)
    SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
    return SessionLocal()

def fix_user_organization():
    """Fix user organization membership"""
    print("🔧 Fixing user organization membership...")
    
    try:
        db = create_db_session()
        
        # Get all users without organization membership
        users_without_org = db.execute(
            text("""
                SELECT u.id, u.email 
                FROM users u 
                LEFT JOIN organization_members om ON u.id = om.user_id 
                WHERE om.user_id IS NULL
            """)
        ).fetchall()
        
        if not users_without_org:
            print("✅ All users already have organization membership")
            return
        
        # Check if default organization exists
        default_org = db.execute(
            text("SELECT id FROM organizations WHERE slug = 'default' LIMIT 1")
        ).fetchone()
        
        if not default_org:
            # Create default organization
            org_id = str(uuid.uuid4())
            db.execute(
                text("""
                    INSERT INTO organizations (
                        id, name, slug, description, size_category, subscription_tier,
                        max_users, max_storage_gb, max_domains, created_at
                    ) VALUES (
                        :id, 'Default Organization', 'default', 'Default organization for users',
                        'small', 'basic', 100, 100, 10, :created_at
                    )
                """),
                {
                    "id": org_id,
                    "created_at": datetime.utcnow()
                }
            )
            print(f"✅ Created default organization: {org_id}")
            
            # Create default general domain
            domain_id = str(uuid.uuid4())
            db.execute(
                text("""
                    INSERT INTO organization_domains (
                        id, organization_id, domain_name, display_name, description,
                        icon, color, is_active, created_at
                    ) VALUES (
                        :id, :org_id, 'general', 'General', 'General knowledge and documentation',
                        'globe', 'blue', :is_active, :created_at
                    )
                """),
                {
                    "id": domain_id,
                    "org_id": org_id,
                    "is_active": True,
                    "created_at": datetime.utcnow()
                }
            )
            print(f"✅ Created default general domain: {domain_id}")
        else:
            org_id = str(default_org.id)
            print(f"✅ Using existing default organization: {org_id}")
        
        # Add users to default organization
        for user in users_without_org:
            member_id = str(uuid.uuid4())
            db.execute(
                text("""
                    INSERT INTO organization_members (
                        id, organization_id, user_id, role, joined_at, is_active
                    ) VALUES (
                        :id, :org_id, :user_id, 'user', :joined_at, :is_active
                    )
                """),
                {
                    "id": member_id,
                    "org_id": org_id,
                    "user_id": str(user.id),
                    "joined_at": datetime.utcnow(),
                    "is_active": True
                }
            )
            print(f"✅ Added user {user.email} to default organization")
        
        db.commit()
        print(f"\n🎉 Fixed organization membership for {len(users_without_org)} users!")
        
    except Exception as e:
        print(f"\n❌ Error fixing user organization: {e}")
        db.rollback()
        raise
    finally:
        db.close()

if __name__ == "__main__":
    fix_user_organization() 
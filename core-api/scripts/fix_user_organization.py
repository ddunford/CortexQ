#!/usr/bin/env python3
"""
Fix user organization membership for users who registered before the bug was fixed
"""

import os
import sys
import uuid
from datetime import datetime
from sqlalchemy import create_engine, text
from sqlalchemy.orm import sessionmaker

def create_db_session():
    """Create database session"""
    database_url = os.getenv('DATABASE_URL', 'postgresql://admin:password@postgres:5432/rag_searcher')
    engine = create_engine(database_url)
    Session = sessionmaker(bind=engine)
    return Session()

def fix_user_organization():
    """Fix user organization membership"""
    print("🔧 Fixing user organization membership...")
    
    try:
        db = create_db_session()
        
        # Get all users without organization membership
        users_without_org = db.execute(
            text("""
                SELECT u.id, u.email, u.full_name 
                FROM users u 
                LEFT JOIN organization_members om ON u.id = om.user_id AND om.is_active = true
                WHERE om.user_id IS NULL
            """)
        ).fetchall()
        
        if not users_without_org:
            print("✅ All users already have organization membership")
            return
        
        print(f"📋 Found {len(users_without_org)} users without organization membership")
        
        for user in users_without_org:
            print(f"\n🔧 Processing user: {user.email}")
            
            # Create organization for this user
            org_id = str(uuid.uuid4())
            org_name = f"{user.full_name or user.email.split('@')[0]}'s Organization"
            org_slug = f"org-{int(datetime.utcnow().timestamp())}-{user.id[:8]}"
            
            # Set default limits for basic tier
            limits = {"max_users": 10, "max_storage_gb": 10, "max_domains": 3}
            
            # Create organization
            db.execute(
                text("""
                    INSERT INTO organizations (
                        id, name, slug, description, logo_url, website, industry,
                        size_category, subscription_tier, max_users, max_storage_gb, max_domains,
                        is_active, created_at
                    ) VALUES (
                        :id, :name, :slug, :description, :logo_url, :website, :industry,
                        :size_category, :subscription_tier, :max_users, :max_storage_gb, :max_domains,
                        :is_active, :created_at
                    )
                """),
                {
                    "id": org_id,
                    "name": org_name,
                    "slug": org_slug,
                    "description": f"Personal workspace for {user.email}",
                    "logo_url": None,
                    "website": None,
                    "industry": None,
                    "size_category": "small",
                    "subscription_tier": "basic",
                    "max_users": limits["max_users"],
                    "max_storage_gb": limits["max_storage_gb"],
                    "max_domains": limits["max_domains"],
                    "is_active": True,
                    "created_at": datetime.utcnow()
                }
            )
            
            # Add user as owner of the organization
            member_id = str(uuid.uuid4())
            db.execute(
                text("""
                    INSERT INTO organization_members (
                        id, organization_id, user_id, role, joined_at, is_active
                    ) VALUES (
                        :id, :org_id, :user_id, 'owner', :joined_at, :is_active
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
            
            # Create default domain for the organization
            domain_id = str(uuid.uuid4())
            db.execute(
                text("""
                    INSERT INTO organization_domains (
                        id, organization_id, domain_name, display_name, description,
                        icon, color, created_by, is_active, created_at
                    ) VALUES (
                        :id, :organization_id, :domain_name, :display_name, :description,
                        :icon, :color, :created_by, :is_active, :created_at
                    )
                """),
                {
                    "id": domain_id,
                    "organization_id": org_id,
                    "domain_name": "general",
                    "display_name": "Knowledge Base",
                    "description": "Main knowledge base for documents and data sources",
                    "icon": "globe",
                    "color": "blue",
                    "created_by": str(user.id),
                    "is_active": True,
                    "created_at": datetime.utcnow()
                }
            )
            
            print(f"✅ Created organization '{org_name}' for user {user.email}")
            print(f"   - Organization ID: {org_id}")
            print(f"   - Domain ID: {domain_id}")
        
        db.commit()
        print(f"\n🎉 Successfully fixed organization membership for {len(users_without_org)} users!")
        
    except Exception as e:
        print(f"\n❌ Error fixing user organization: {e}")
        db.rollback()
        raise
    finally:
        db.close()

if __name__ == "__main__":
    fix_user_organization() 
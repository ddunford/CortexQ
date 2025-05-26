#!/usr/bin/env python3
"""
Database seeding script for Enterprise RAG System
Populates initial roles, permissions, and role-permission mappings
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

def seed_permissions(db):
    """Seed basic permissions"""
    permissions = [
        {
            "name": "chat:read",
            "description": "Read chat messages and sessions",
            "resource": "chat",
            "action": "read"
        },
        {
            "name": "chat:write", 
            "description": "Send chat messages and create sessions",
            "resource": "chat",
            "action": "write"
        },
        {
            "name": "files:read",
            "description": "View and download files",
            "resource": "files",
            "action": "read"
        },
        {
            "name": "files:write",
            "description": "Upload and manage files",
            "resource": "files",
            "action": "write"
        },
        {
            "name": "files:delete",
            "description": "Delete files",
            "resource": "files", 
            "action": "delete"
        },
        {
            "name": "users:read",
            "description": "View user information",
            "resource": "users",
            "action": "read"
        },
        {
            "name": "users:create",
            "description": "Create new users",
            "resource": "users",
            "action": "create"
        },
        {
            "name": "users:update",
            "description": "Update user information",
            "resource": "users",
            "action": "update"
        },
        {
            "name": "users:delete",
            "description": "Delete users",
            "resource": "users",
            "action": "delete"
        },
        {
            "name": "roles:read",
            "description": "View roles and permissions",
            "resource": "roles",
            "action": "read"
        },
        {
            "name": "roles:create",
            "description": "Create new roles",
            "resource": "roles",
            "action": "create"
        },
        {
            "name": "roles:update",
            "description": "Update roles and permissions",
            "resource": "roles",
            "action": "update"
        },
        {
            "name": "roles:delete",
            "description": "Delete roles",
            "resource": "roles",
            "action": "delete"
        },
        {
            "name": "search:read",
            "description": "Search and retrieve content",
            "resource": "search",
            "action": "read"
        },
        {
            "name": "search:write",
            "description": "Advanced search operations",
            "resource": "search",
            "action": "write"
        },
        {
            "name": "analytics:read",
            "description": "View analytics and reports",
            "resource": "analytics",
            "action": "read"
        },
        {
            "name": "admin:all",
            "description": "Full administrative access",
            "resource": "admin",
            "action": "all"
        }
    ]
    
    print("🔑 Seeding permissions...")
    for perm in permissions:
        # Check if permission already exists
        existing = db.execute(
            text("SELECT id FROM permissions WHERE name = :name"),
            {"name": perm["name"]}
        ).fetchone()
        
        if not existing:
            perm_id = str(uuid.uuid4())
            db.execute(
                text("""
                    INSERT INTO permissions (id, name, description, resource, action, created_at)
                    VALUES (:id, :name, :description, :resource, :action, :created_at)
                """),
                {
                    "id": perm_id,
                    "name": perm["name"],
                    "description": perm["description"],
                    "resource": perm["resource"],
                    "action": perm["action"],
                    "created_at": datetime.utcnow()
                }
            )
            print(f"  ✅ Created permission: {perm['name']}")
        else:
            print(f"  ⏭️ Permission already exists: {perm['name']}")

def seed_roles(db):
    """Seed basic roles"""
    roles = [
        {
            "name": "admin",
            "description": "Administrator with full access",
            "permissions": [
                "chat:read", "chat:write", "files:read", "files:write", "files:delete",
                "users:read", "users:create", "users:update", "users:delete",
                "roles:read", "roles:create", "roles:update", "roles:delete",
                "search:read", "search:write", "analytics:read", "admin:all"
            ],
            "domain_access": ["*"]  # All domains
        },
        {
            "name": "user",
            "description": "Standard user with basic access",
            "permissions": [
                "chat:read", "chat:write", "files:read", "files:write", 
                "search:read", "analytics:read"
            ],
            "domain_access": ["general"]
        },
        {
            "name": "viewer",
            "description": "Read-only access",
            "permissions": [
                "chat:read", "files:read", "search:read"
            ],
            "domain_access": ["general"]
        },
        {
            "name": "support",
            "description": "Support team with extended access",
            "permissions": [
                "chat:read", "chat:write", "files:read", "files:write",
                "users:read", "search:read", "analytics:read"
            ],
            "domain_access": ["general", "support"]
        }
    ]
    
    print("\n👥 Seeding roles...")
    for role in roles:
        # Check if role already exists
        existing = db.execute(
            text("SELECT id FROM roles WHERE name = :name"),
            {"name": role["name"]}
        ).fetchone()
        
        if not existing:
            role_id = str(uuid.uuid4())
            db.execute(
                text("""
                    INSERT INTO roles (id, name, description, permissions, domain_access, created_at)
                    VALUES (:id, :name, :description, :permissions, :domain_access, :created_at)
                """),
                {
                    "id": role_id,
                    "name": role["name"],
                    "description": role["description"],
                    "permissions": str(role["permissions"]).replace("'", '"'),  # Convert to JSON string
                    "domain_access": str(role["domain_access"]).replace("'", '"'),
                    "created_at": datetime.utcnow()
                }
            )
            print(f"  ✅ Created role: {role['name']}")
        else:
            print(f"  ⏭️ Role already exists: {role['name']}")

def seed_role_permissions(db):
    """Create role-permission mappings"""
    print("\n🔗 Creating role-permission mappings...")
    
    # Get all roles and permissions
    roles = db.execute(text("SELECT id, name FROM roles")).fetchall()
    permissions = db.execute(text("SELECT id, name FROM permissions")).fetchall()
    
    # Create mappings based on role definitions
    role_permission_map = {
        "admin": [
            "chat:read", "chat:write", "files:read", "files:write", "files:delete",
            "users:read", "users:create", "users:update", "users:delete",
            "roles:read", "roles:create", "roles:update", "roles:delete",
            "search:read", "search:write", "analytics:read", "admin:all"
        ],
        "user": [
            "chat:read", "chat:write", "files:read", "files:write", 
            "search:read", "analytics:read"
        ],
        "viewer": [
            "chat:read", "files:read", "search:read"
        ],
        "support": [
            "chat:read", "chat:write", "files:read", "files:write",
            "users:read", "search:read", "analytics:read"
        ]
    }
    
    # Create permission lookup
    perm_lookup = {perm.name: perm.id for perm in permissions}
    
    for role in roles:
        role_perms = role_permission_map.get(role.name, [])
        
        for perm_name in role_perms:
            if perm_name in perm_lookup:
                # Check if mapping already exists
                existing = db.execute(
                    text("""
                        SELECT 1 FROM role_permissions 
                        WHERE role_id = :role_id AND permission_id = :permission_id
                    """),
                    {"role_id": str(role.id), "permission_id": str(perm_lookup[perm_name])}
                ).fetchone()
                
                if not existing:
                    db.execute(
                        text("""
                            INSERT INTO role_permissions (role_id, permission_id, granted_at)
                            VALUES (:role_id, :permission_id, :granted_at)
                        """),
                        {
                            "role_id": str(role.id),
                            "permission_id": str(perm_lookup[perm_name]),
                            "granted_at": datetime.utcnow()
                        }
                    )
                    print(f"  ✅ Mapped {role.name} -> {perm_name}")
                else:
                    print(f"  ⏭️ Mapping already exists: {role.name} -> {perm_name}")

def seed_domain_templates(db):
    """Seed domain templates"""
    templates = [
        {
            "name": "general",
            "display_name": "General Knowledge",
            "description": "General purpose knowledge domain",
            "icon": "globe",
            "color": "blue",
            "category": "general",
            "suggested_settings": {
                "max_file_size_mb": 50,
                "allowed_file_types": ["pdf", "docx", "txt", "md", "json", "csv"],
                "embedding_model": "all-MiniLM-L6-v2",
                "chunk_size": 1000,
                "chunk_overlap": 200
            }
        },
        {
            "name": "support",
            "display_name": "Customer Support",
            "description": "Customer support knowledge base",
            "icon": "headphones",
            "color": "green",
            "category": "support",
            "suggested_settings": {
                "max_file_size_mb": 25,
                "allowed_file_types": ["pdf", "docx", "txt", "md"],
                "embedding_model": "all-MiniLM-L6-v2",
                "chunk_size": 800,
                "chunk_overlap": 150
            }
        },
        {
            "name": "engineering",
            "display_name": "Engineering Docs",
            "description": "Technical documentation and code",
            "icon": "code",
            "color": "purple",
            "category": "technical",
            "suggested_settings": {
                "max_file_size_mb": 100,
                "allowed_file_types": ["pdf", "md", "txt", "py", "js", "json", "yaml"],
                "embedding_model": "all-MiniLM-L6-v2",
                "chunk_size": 1200,
                "chunk_overlap": 300
            }
        },
        {
            "name": "sales",
            "display_name": "Sales Materials",
            "description": "Sales documentation and materials",
            "icon": "chart-line",
            "color": "orange",
            "category": "business",
            "suggested_settings": {
                "max_file_size_mb": 50,
                "allowed_file_types": ["pdf", "docx", "pptx", "txt"],
                "embedding_model": "all-MiniLM-L6-v2",
                "chunk_size": 1000,
                "chunk_overlap": 200
            }
        }
    ]
    
    print("\n📋 Seeding domain templates...")
    for template in templates:
        # Check if template already exists
        existing = db.execute(
            text("SELECT id FROM domain_templates WHERE name = :name"),
            {"name": template["name"]}
        ).fetchone()
        
        if not existing:
            template_id = str(uuid.uuid4())
            db.execute(
                text("""
                    INSERT INTO domain_templates (
                        id, name, display_name, description, icon, color, 
                        category, suggested_settings, created_at
                    ) VALUES (
                        :id, :name, :display_name, :description, :icon, :color,
                        :category, :suggested_settings, :created_at
                    )
                """),
                {
                    "id": template_id,
                    "name": template["name"],
                    "display_name": template["display_name"],
                    "description": template["description"],
                    "icon": template["icon"],
                    "color": template["color"],
                    "category": template["category"],
                    "suggested_settings": str(template["suggested_settings"]).replace("'", '"'),
                    "created_at": datetime.utcnow()
                }
            )
            print(f"  ✅ Created template: {template['name']}")
        else:
            print(f"  ⏭️ Template already exists: {template['name']}")

def main():
    """Main seeding function"""
    print("🌱 Starting database seeding...")
    
    try:
        db = create_db_session()
        
        # Seed in order (permissions first, then roles, then mappings)
        seed_permissions(db)
        seed_roles(db)
        seed_role_permissions(db)
        seed_domain_templates(db)
        
        # Commit all changes
        db.commit()
        print("\n🎉 Database seeding completed successfully!")
        
    except Exception as e:
        print(f"\n❌ Error during seeding: {e}")
        db.rollback()
        raise
    finally:
        db.close()

if __name__ == "__main__":
    main() 
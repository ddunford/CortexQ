#!/usr/bin/env python3
"""
Create database tables from SQLAlchemy models
"""
import os
import sys
sys.path.append('/app/src')

from models import Base
from sqlalchemy import create_engine, text

def create_tables():
    """Create all database tables"""
    # Create engine
    database_url = os.getenv('DATABASE_URL', 'postgresql://admin:password@postgres:5432/rag_searcher')
    engine = create_engine(database_url)
    
    # Create pgvector extension
    with engine.connect() as conn:
        conn.execute(text("CREATE EXTENSION IF NOT EXISTS vector;"))
        conn.commit()
    
    # Create all tables
    Base.metadata.create_all(engine)
    print('✅ All tables created successfully')
    
    # Insert default data
    from sqlalchemy.orm import sessionmaker
    Session = sessionmaker(bind=engine)
    session = Session()
    
    try:
        # Insert default organization
        from models import Organization, User, OrganizationMember
        
        # Check if default org exists
        default_org = session.query(Organization).filter_by(slug='default').first()
        if not default_org:
            default_org = Organization(
                name='Default Organization',
                slug='default',
                description='Default organization for single-tenant setup'
            )
            session.add(default_org)
            session.commit()
            print('✅ Default organization created')
        
        # Check if admin user exists
        admin_user = session.query(User).filter_by(username='admin').first()
        if not admin_user:
            admin_user = User(
                username='admin',
                email='admin@example.com',
                full_name='System Administrator',
                password_hash='$2b$12$LQv3c1yqBWVHxkd0LHAkCOYz6TtxMQJqhN8/LewdBPj8xqUx3QJlC',  # admin123
                is_superuser=True
            )
            session.add(admin_user)
            session.commit()
            print('✅ Admin user created')
        
        # Add admin to default organization
        membership = session.query(OrganizationMember).filter_by(
            organization_id=default_org.id,
            user_id=admin_user.id
        ).first()
        
        if not membership:
            membership = OrganizationMember(
                organization_id=default_org.id,
                user_id=admin_user.id,
                role='admin',
                is_active=True
            )
            session.add(membership)
            session.commit()
            print('✅ Admin user added to default organization')
            
    except Exception as e:
        print(f'⚠️ Error creating default data: {e}')
        session.rollback()
    finally:
        session.close()

if __name__ == '__main__':
    create_tables() 
#!/usr/bin/env python3
"""
Create database tables directly from SQLAlchemy models
"""
import os
import sys
from sqlalchemy import create_engine, text
from sqlalchemy.orm import sessionmaker

# Add src to path
sys.path.append('/app/src')

from models import Base, Organization, User, OrganizationMember

def create_tables():
    """Create all database tables"""
    # Create engine
    database_url = os.getenv('DATABASE_URL', 'postgresql://admin:password@postgres:5432/rag_searcher')
    engine = create_engine(database_url)
    
    print("Creating all tables...")
    # Create all tables
    Base.metadata.create_all(engine)
    print('✅ All tables created successfully')
    
    # Insert default data
    Session = sessionmaker(bind=engine)
    session = Session()
    
    try:
        # Create default organization
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
        
        # Create admin user
        admin_user = session.query(User).filter_by(username='admin').first()
        if not admin_user:
            admin_user = User(
                username='admin',
                email='admin@example.com',
                full_name='System Administrator',
                password_hash='$2b$12$LQv3c1yqBWVHxkd0LHAkCOYz6TtxMQJqhN8/LewdBPj8xqUx3QJlC',  # admin123
                is_superuser=True,
                primary_organization_id=default_org.id
            )
            session.add(admin_user)
            session.commit()
            print('✅ Admin user created')
        
        # Add admin to organization
        membership = session.query(OrganizationMember).filter_by(
            organization_id=default_org.id,
            user_id=admin_user.id
        ).first()
        if not membership:
            membership = OrganizationMember(
                organization_id=default_org.id,
                user_id=admin_user.id,
                role='owner',
                is_active=True
            )
            session.add(membership)
            session.commit()
            print('✅ Admin user added to organization')
            
    except Exception as e:
        print(f'❌ Error creating default data: {e}')
        session.rollback()
    finally:
        session.close()

if __name__ == '__main__':
    create_tables() 
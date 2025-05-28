#!/bin/bash

# Simplified CortexQ Core API Startup Script
# Bypasses Alembic migrations and starts application directly

set -e

echo "🚀 Starting CortexQ Core API (Simple Mode)..."

# Wait for database to be ready
echo "⏳ Waiting for database connection..."
python -c "
import os
import time
import psycopg2
from psycopg2 import OperationalError

database_url = os.getenv('DATABASE_URL', 'postgresql://admin:password@postgres:5432/cortexq')

# Parse database URL
if database_url.startswith('postgresql://'):
    # Extract connection parameters
    import urllib.parse
    parsed = urllib.parse.urlparse(database_url)
    
    max_retries = 30
    retry_count = 0
    
    while retry_count < max_retries:
        try:
            conn = psycopg2.connect(
                host=parsed.hostname,
                port=parsed.port or 5432,
                user=parsed.username,
                password=parsed.password,
                database=parsed.path[1:]  # Remove leading slash
            )
            conn.close()
            print('✅ Database connection successful')
            break
        except OperationalError as e:
            retry_count += 1
            print(f'⏳ Database not ready (attempt {retry_count}/{max_retries}): {e}')
            time.sleep(2)
    else:
        print('❌ Failed to connect to database after 30 attempts')
        exit(1)
"

echo "✅ Database connection verified"

# Create pgvector extension and check tables
echo "🔍 Checking database schema..."
python -c "
import os
import psycopg2
from sqlalchemy import create_engine, text
from sqlalchemy.orm import sessionmaker

database_url = os.getenv('DATABASE_URL', 'postgresql://admin:password@postgres:5432/cortexq')
engine = create_engine(database_url)

# Create pgvector extension first
with engine.connect() as conn:
    conn.execute(text('CREATE EXTENSION IF NOT EXISTS vector;'))
    conn.commit()
    print('✅ pgvector extension ready')

# Check if tables exist
with engine.connect() as conn:
    result = conn.execute(text(\"\"\"
        SELECT COUNT(*) as table_count 
        FROM information_schema.tables 
        WHERE table_schema = 'public' 
        AND table_name IN ('users', 'organizations', 'roles', 'permissions')
    \"\"\"))
    table_count = result.fetchone()[0]
    
    if table_count < 4:
        print('🆕 Fresh database detected - creating tables...')
        # Import and create all tables
        import sys
        sys.path.append('src')
        from models import Base
        Base.metadata.create_all(bind=engine)
        
        # Add UUID defaults for all ID columns
        print('🔧 Adding UUID defaults to ID columns...')
        uuid_tables = [
            'roles', 'permissions', 'organizations', 'domain_templates', 'users',
            'workflow_executions', 'user_sessions', 'organization_domains', 
            'organization_invitations', 'audit_events', 'files', 'chat_sessions',
            'classification_results', 'rag_executions', 'organization_members',
            'user_roles', 'role_permissions', 'embeddings', 'chat_messages',
            'connectors', 'sync_jobs'
        ]
        
        for table in uuid_tables:
            try:
                conn.execute(text(f'ALTER TABLE {table} ALTER COLUMN id SET DEFAULT gen_random_uuid();'))
            except Exception as e:
                print(f'⚠️  Warning: Could not set UUID default for {table}: {e}')
        
        conn.commit()
        print('✅ Database tables created successfully with UUID defaults')
    else:
        print('✅ Database tables already exist')
"

# Run database seeding for RBAC setup
echo "🌱 Initializing RBAC system (roles, permissions, defaults)..."
python scripts/seed_database.py

echo "✅ Database initialization completed successfully"

# Start the application directly
echo "🎯 Starting Core API application..."
exec python src/main.py 
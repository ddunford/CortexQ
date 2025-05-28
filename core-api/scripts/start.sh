#!/bin/bash

# CortexQ Core API Startup Script
# Handles database migrations and application startup

set -e

echo "🚀 Starting CortexQ Core API..."

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

# Check if this is a fresh deployment (no alembic_version table)
echo "🔍 Checking database schema status..."
FRESH_DEPLOY=$(python -c "
import os
import psycopg2
from psycopg2 import OperationalError

database_url = os.getenv('DATABASE_URL', 'postgresql://admin:password@postgres:5432/cortexq')

try:
    import urllib.parse
    parsed = urllib.parse.urlparse(database_url)
    
    conn = psycopg2.connect(
        host=parsed.hostname,
        port=parsed.port or 5432,
        user=parsed.username,
        password=parsed.password,
        database=parsed.path[1:]
    )
    
    cursor = conn.cursor()
    cursor.execute(\"\"\"
        SELECT EXISTS (
            SELECT FROM information_schema.tables 
            WHERE table_schema = 'public' 
            AND table_name = 'alembic_version'
        );
    \"\"\")
    
    table_exists = cursor.fetchone()[0]
    cursor.close()
    conn.close()
    
    if table_exists:
        print('existing')
    else:
        print('fresh')
        
except Exception as e:
    print('fresh')  # Assume fresh on any error
")

if [ "$FRESH_DEPLOY" = "fresh" ]; then
    echo "🆕 Fresh deployment detected - creating initial schema..."
    
    # Create pgvector extension if it doesn't exist
    echo "📦 Ensuring pgvector extension is available..."
    python -c "
import os
import psycopg2

database_url = os.getenv('DATABASE_URL', 'postgresql://admin:password@postgres:5432/cortexq')

try:
    import urllib.parse
    parsed = urllib.parse.urlparse(database_url)
    
    conn = psycopg2.connect(
        host=parsed.hostname,
        port=parsed.port or 5432,
        user=parsed.username,
        password=parsed.password,
        database=parsed.path[1:]
    )
    
    conn.autocommit = True
    cursor = conn.cursor()
    cursor.execute('CREATE EXTENSION IF NOT EXISTS vector;')
    cursor.close()
    conn.close()
    
    print('✅ pgvector extension ready')
    
except Exception as e:
    print(f'⚠️  Warning: Could not create pgvector extension: {e}')
"
    
    # Generate and apply initial migration
    echo "📝 Generating initial migration..."
    alembic revision --autogenerate -m "Initial schema with organization isolation"
    
    echo "⬆️  Applying initial migration..."
    alembic upgrade head
    
else
    echo "🔄 Existing deployment detected - applying pending migrations..."
    alembic upgrade head
fi

echo "✅ Database migrations completed successfully"

# Run database seeding for RBAC setup
echo "🌱 Initializing RBAC system (roles, permissions, defaults)..."
python scripts/seed_database.py

echo "✅ Database initialization completed successfully"

# Start the application
echo "🎯 Starting Core API application..."
exec python src/main.py 
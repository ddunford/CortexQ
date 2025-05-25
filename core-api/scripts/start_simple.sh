#!/bin/bash

# Simplified Enterprise RAG Core API Startup Script
# Bypasses Alembic migrations and starts application directly

set -e

echo "🚀 Starting Enterprise RAG Core API (Simple Mode)..."

# Wait for database to be ready
echo "⏳ Waiting for database connection..."
python -c "
import os
import time
import psycopg2
from psycopg2 import OperationalError

database_url = os.getenv('DATABASE_URL', 'postgresql://admin:password@postgres:5432/rag_searcher')

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

# Start the application directly
echo "🎯 Starting Core API application..."
exec python src/main.py 
#!/usr/bin/env python3

import asyncio
import sys
import os
import logging
from datetime import datetime

# Add the src directory to Python path
sys.path.insert(0, '/app/src')

# Set up logging to see detailed output
logging.basicConfig(
    level=logging.DEBUG,  # Set to DEBUG to see all our detailed logs
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)

async def trigger_web_scraper_debug():
    """Trigger web scraper with debug logging"""
    
    print("🚀 Triggering web scraper with debug logging...")
    
    try:
        from services.connector_service import ConnectorService
        from services.oauth_service import OAuthService
        from sqlalchemy import create_engine
        from sqlalchemy.orm import sessionmaker
        
        # Create database connection
        DATABASE_URL = "postgresql://admin:password@postgres:5432/cortexq"
        engine = create_engine(DATABASE_URL)
        SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
        db = SessionLocal()
        
        # Create connector service
        oauth_service = OAuthService()
        connector_service = ConnectorService(db, oauth_service)
        
        # Get the web scraper connector ID
        connector_id = "365baeea-74c8-4b74-af8f-9b70da22e77e"
        organization_id = "782cc1a2-0de3-49bd-9317-d18dbe93d62c" # This is actually domain_id from our query
        
        print(f"🔧 Starting sync for connector {connector_id}")
        
        # Trigger the sync
        result = await connector_service.sync_connector(
            connector_id=connector_id,
            organization_id=organization_id,
            full_sync=True
        )
        
        print(f"🎉 Sync result: {result}")
        
    except Exception as e:
        print(f"❌ Error triggering sync: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    asyncio.run(trigger_web_scraper_debug()) 
"""
Audit Service - Main Application
Provides comprehensive audit logging, compliance reporting, and security monitoring
"""

import uuid
from datetime import datetime, timedelta
from typing import List, Optional, Dict, Any, Union
from enum import Enum

import uvicorn
from fastapi import FastAPI, HTTPException, Depends, status, Request, Query
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy import create_engine, text, func, and_, or_
from sqlalchemy.orm import sessionmaker, Session
from sqlalchemy.types import Text
from pydantic import BaseModel, Field
import redis
import logging
import json

from config import settings
from models import Base, AuditEvent, ComplianceReport, SecurityAlert, HealthResponse, AuditEventCreate
from audit_utils import AuditLogger, ComplianceManager, SecurityMonitor

# Configure logging
logging.basicConfig(level=getattr(logging, settings.LOG_LEVEL.upper()))
logger = logging.getLogger(__name__)

# Database setup
engine = create_engine(settings.DATABASE_URL)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

# Redis setup
try:
    redis_client = redis.from_url(settings.REDIS_URL)
    redis_client.ping()
    logger.info("Connected to Redis")
except Exception as e:
    logger.warning(f"Redis connection failed: {e}")
    redis_client = None

# FastAPI app
app = FastAPI(
    title="Audit Service",
    description="Comprehensive audit logging and compliance service",
    version=settings.SERVICE_VERSION,
    docs_url="/docs",
    redoc_url="/redoc"
)

# CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins_list,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Database dependency
def get_db():
    """Get database session"""
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

# Simple auth dependency (in production, this would verify JWT from auth service)
async def verify_admin_access(request: Request):
    """Verify admin access (simplified for now)"""
    # In production, this would call the auth service to verify admin role
    auth_header = request.headers.get("authorization")
    if not auth_header or not auth_header.startswith("Bearer "):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Authorization required"
        )
    # For now, we'll assume valid token = admin access
    return True

# Startup event
@app.on_event("startup")
async def startup_event():
    """Initialize database and start monitoring"""
    
    # Create tables
    Base.metadata.create_all(bind=engine)
    logger.info("Database tables created")
    
    # Initialize security monitoring
    SecurityMonitor.start_monitoring()
    logger.info("Security monitoring started")

# Health check
@app.get("/health", response_model=HealthResponse)
async def health_check():
    """Health check endpoint"""
    
    # Check database
    db_healthy = True
    try:
        db = SessionLocal()
        db.execute(text("SELECT 1"))
        db.close()
    except Exception:
        db_healthy = False
    
    # Check cache
    cache_healthy = True
    if redis_client:
        try:
            redis_client.ping()
        except Exception:
            cache_healthy = False
    else:
        cache_healthy = False
    
    return HealthResponse(
        status="healthy" if db_healthy and cache_healthy else "degraded",
        service="audit-service",
        version=settings.SERVICE_VERSION,
        timestamp=datetime.utcnow(),
        database_healthy=db_healthy,
        cache_healthy=cache_healthy
    )

# Audit logging endpoints
@app.post("/audit/events")
async def log_audit_event(
    event: AuditEventCreate,
    request: Request,
    db: Session = Depends(get_db)
):
    """Log an audit event"""
    
    try:
        # Create SQLAlchemy audit event from Pydantic model
        audit_event = AuditEvent(
            event_type=event.event_type,
            event_description=event.event_description,
            user_id=event.user_id,
            resource=event.resource,
            action=event.action,
            session_id=event.session_id,
            event_metadata=event.event_metadata,
            tags=event.tags,
            compliance_relevant=event.compliance_relevant,
            security_relevant=event.security_relevant,
            risk_level=event.risk_level,
            ip_address=request.client.host,
            user_agent=request.headers.get("user-agent", ""),
            request_id=request.headers.get("x-request-id"),
            created_at=datetime.utcnow()
        )
        
        # Store in database
        AuditLogger.log_event(db, audit_event)
        
        # Check for security patterns
        SecurityMonitor.check_security_patterns(db, audit_event)
        
        return {"message": "Event logged successfully", "event_id": str(audit_event.id)}
        
    except Exception as e:
        logger.error(f"Failed to log audit event: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to log audit event"
        )

@app.get("/audit/events")
async def get_audit_events(
    skip: int = Query(0, ge=0),
    limit: int = Query(100, ge=1, le=1000),
    event_type: Optional[str] = Query(None),
    user_id: Optional[str] = Query(None),
    resource: Optional[str] = Query(None),
    start_date: Optional[datetime] = Query(None),
    end_date: Optional[datetime] = Query(None),
    admin_access: bool = Depends(verify_admin_access),
    db: Session = Depends(get_db)
):
    """Get audit events with filtering"""
    
    query = db.query(AuditEvent)
    
    # Apply filters
    if event_type:
        query = query.filter(AuditEvent.event_type == event_type)
    if user_id:
        query = query.filter(AuditEvent.user_id == user_id)
    if resource:
        query = query.filter(AuditEvent.resource == resource)
    if start_date:
        query = query.filter(AuditEvent.created_at >= start_date)
    if end_date:
        query = query.filter(AuditEvent.created_at <= end_date)
    
    # Get total count
    total = query.count()
    
    # Apply pagination and ordering
    events = query.order_by(AuditEvent.created_at.desc()).offset(skip).limit(limit).all()
    
    return {
        "events": [event.to_dict() for event in events],
        "total": total,
        "skip": skip,
        "limit": limit
    }

@app.get("/audit/events/{event_id}")
async def get_audit_event(
    event_id: str,
    admin_access: bool = Depends(verify_admin_access),
    db: Session = Depends(get_db)
):
    """Get specific audit event"""
    
    event = db.query(AuditEvent).filter(AuditEvent.id == event_id).first()
    if not event:
        raise HTTPException(status_code=404, detail="Audit event not found")
    
    return event.to_dict()

# Analytics endpoints
@app.get("/audit/analytics/summary")
async def get_audit_summary(
    days: int = Query(7, ge=1, le=365),
    admin_access: bool = Depends(verify_admin_access),
    db: Session = Depends(get_db)
):
    """Get audit summary analytics"""
    
    start_date = datetime.utcnow() - timedelta(days=days)
    
    # Event counts by type
    event_counts = db.query(
        AuditEvent.event_type,
        func.count(AuditEvent.id).label('count')
    ).filter(
        AuditEvent.created_at >= start_date
    ).group_by(AuditEvent.event_type).all()
    
    # Events by hour (last 24h)
    hourly_events = db.query(
        func.date_trunc('hour', AuditEvent.created_at).label('hour'),
        func.count(AuditEvent.id).label('count')
    ).filter(
        AuditEvent.created_at >= datetime.utcnow() - timedelta(hours=24)
    ).group_by(func.date_trunc('hour', AuditEvent.created_at)).all()
    
    # Top users by activity
    top_users = db.query(
        AuditEvent.user_id,
        func.count(AuditEvent.id).label('count')
    ).filter(
        AuditEvent.created_at >= start_date,
        AuditEvent.user_id.isnot(None)
    ).group_by(AuditEvent.user_id).order_by(func.count(AuditEvent.id).desc()).limit(10).all()
    
    # Security events
    security_events = db.query(func.count(AuditEvent.id)).filter(
        AuditEvent.created_at >= start_date,
        AuditEvent.event_type.in_(['login_failed', 'permission_denied', 'suspicious_activity'])
    ).scalar()
    
    return {
        "period_days": days,
        "event_counts": [{"type": et, "count": c} for et, c in event_counts],
        "hourly_events": [{"hour": h.isoformat(), "count": c} for h, c in hourly_events],
        "top_users": [{"user_id": u, "count": c} for u, c in top_users],
        "security_events": security_events or 0,
        "total_events": sum(c for _, c in event_counts)
    }

@app.get("/audit/analytics/compliance")
async def get_compliance_analytics(
    admin_access: bool = Depends(verify_admin_access),
    db: Session = Depends(get_db)
):
    """Get compliance analytics"""
    
    return ComplianceManager.get_compliance_summary(db)

@app.get("/audit/analytics/security")
async def get_security_analytics(
    hours: int = Query(24, ge=1, le=168),
    admin_access: bool = Depends(verify_admin_access),
    db: Session = Depends(get_db)
):
    """Get security analytics"""
    
    start_time = datetime.utcnow() - timedelta(hours=hours)
    
    # Failed login attempts
    failed_logins = db.query(func.count(AuditEvent.id)).filter(
        AuditEvent.created_at >= start_time,
        AuditEvent.event_type == 'login_failed'
    ).scalar()
    
    # Permission denials
    permission_denials = db.query(func.count(AuditEvent.id)).filter(
        AuditEvent.created_at >= start_time,
        AuditEvent.event_type == 'permission_denied'
    ).scalar()
    
    # Suspicious activities
    suspicious_activities = db.query(func.count(AuditEvent.id)).filter(
        AuditEvent.created_at >= start_time,
        AuditEvent.event_type == 'suspicious_activity'
    ).scalar()
    
    # Top IP addresses with failures
    top_failing_ips = db.query(
        AuditEvent.ip_address,
        func.count(AuditEvent.id).label('count')
    ).filter(
        AuditEvent.created_at >= start_time,
        AuditEvent.event_type.in_(['login_failed', 'permission_denied']),
        AuditEvent.ip_address.isnot(None)
    ).group_by(AuditEvent.ip_address).order_by(func.count(AuditEvent.id).desc()).limit(10).all()
    
    return {
        "period_hours": hours,
        "failed_logins": failed_logins or 0,
        "permission_denials": permission_denials or 0,
        "suspicious_activities": suspicious_activities or 0,
        "top_failing_ips": [{"ip": ip, "count": c} for ip, c in top_failing_ips],
        "security_score": SecurityMonitor.calculate_security_score(
            failed_logins or 0, permission_denials or 0, suspicious_activities or 0
        )
    }

# Compliance endpoints
@app.post("/audit/compliance/report")
async def generate_compliance_report(
    report_type: str = Query(..., pattern="^(gdpr|ccpa|sox|custom)$"),
    start_date: datetime = Query(...),
    end_date: datetime = Query(...),
    admin_access: bool = Depends(verify_admin_access),
    db: Session = Depends(get_db)
):
    """Generate compliance report"""
    
    try:
        report = ComplianceManager.generate_report(
            db, report_type, start_date, end_date
        )
        
        # Store report
        compliance_report = ComplianceReport(
            report_type=report_type,
            start_date=start_date,
            end_date=end_date,
            report_data=report,
            generated_at=datetime.utcnow()
        )
        db.add(compliance_report)
        db.commit()
        
        return {
            "report_id": str(compliance_report.id),
            "report": report,
            "generated_at": compliance_report.generated_at
        }
        
    except Exception as e:
        logger.error(f"Failed to generate compliance report: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to generate compliance report"
        )

@app.get("/audit/compliance/reports")
async def list_compliance_reports(
    skip: int = Query(0, ge=0),
    limit: int = Query(50, ge=1, le=200),
    report_type: Optional[str] = Query(None),
    admin_access: bool = Depends(verify_admin_access),
    db: Session = Depends(get_db)
):
    """List compliance reports"""
    
    query = db.query(ComplianceReport)
    
    if report_type:
        query = query.filter(ComplianceReport.report_type == report_type)
    
    total = query.count()
    reports = query.order_by(ComplianceReport.generated_at.desc()).offset(skip).limit(limit).all()
    
    return {
        "reports": [
            {
                "id": str(report.id),
                "report_type": report.report_type,
                "start_date": report.start_date,
                "end_date": report.end_date,
                "generated_at": report.generated_at
            }
            for report in reports
        ],
        "total": total,
        "skip": skip,
        "limit": limit
    }

@app.get("/audit/compliance/reports/{report_id}")
async def get_compliance_report(
    report_id: str,
    admin_access: bool = Depends(verify_admin_access),
    db: Session = Depends(get_db)
):
    """Get specific compliance report"""
    
    report = db.query(ComplianceReport).filter(ComplianceReport.id == report_id).first()
    if not report:
        raise HTTPException(status_code=404, detail="Compliance report not found")
    
    return {
        "id": str(report.id),
        "report_type": report.report_type,
        "start_date": report.start_date,
        "end_date": report.end_date,
        "report_data": report.report_data,
        "generated_at": report.generated_at
    }

# Data retention endpoints
@app.post("/audit/retention/cleanup")
async def cleanup_old_data(
    days: int = Query(90, ge=1, le=3650),
    dry_run: bool = Query(True),
    admin_access: bool = Depends(verify_admin_access),
    db: Session = Depends(get_db)
):
    """Cleanup old audit data based on retention policy"""
    
    cutoff_date = datetime.utcnow() - timedelta(days=days)
    
    # Count events to be deleted
    count = db.query(AuditEvent).filter(AuditEvent.created_at < cutoff_date).count()
    
    if dry_run:
        return {
            "dry_run": True,
            "events_to_delete": count,
            "cutoff_date": cutoff_date,
            "message": f"Would delete {count} events older than {days} days"
        }
    
    # Perform actual deletion
    deleted = db.query(AuditEvent).filter(AuditEvent.created_at < cutoff_date).delete()
    db.commit()
    
    # Log the cleanup
    AuditLogger.log_event(db, AuditEvent(
        event_type="data_cleanup",
        event_description=f"Deleted {deleted} audit events older than {days} days",
        resource="audit_events",
        action="delete",
        event_metadata={"deleted_count": deleted, "cutoff_date": cutoff_date.isoformat()}
    ))
    
    return {
        "dry_run": False,
        "events_deleted": deleted,
        "cutoff_date": cutoff_date,
        "message": f"Successfully deleted {deleted} events older than {days} days"
    }

# Search and export endpoints
@app.get("/audit/search")
async def search_audit_events(
    query: str = Query(..., min_length=3),
    skip: int = Query(0, ge=0),
    limit: int = Query(100, ge=1, le=1000),
    admin_access: bool = Depends(verify_admin_access),
    db: Session = Depends(get_db)
):
    """Search audit events by text query"""
    
    # Search in event descriptions and metadata
    search_filter = or_(
        AuditEvent.event_description.ilike(f"%{query}%"),
        AuditEvent.resource.ilike(f"%{query}%"),
        func.cast(AuditEvent.event_metadata, Text).ilike(f"%{query}%")
    )
    
    query_obj = db.query(AuditEvent).filter(search_filter)
    total = query_obj.count()
    
    events = query_obj.order_by(AuditEvent.created_at.desc()).offset(skip).limit(limit).all()
    
    return {
        "events": [event.to_dict() for event in events],
        "total": total,
        "skip": skip,
        "limit": limit,
        "query": query
    }

@app.get("/audit/export")
async def export_audit_events(
    format: str = Query("json", pattern="^(json|csv)$"),
    start_date: Optional[datetime] = Query(None),
    end_date: Optional[datetime] = Query(None),
    event_type: Optional[str] = Query(None),
    admin_access: bool = Depends(verify_admin_access),
    db: Session = Depends(get_db)
):
    """Export audit events"""
    
    query = db.query(AuditEvent)
    
    # Apply filters
    if start_date:
        query = query.filter(AuditEvent.created_at >= start_date)
    if end_date:
        query = query.filter(AuditEvent.created_at <= end_date)
    if event_type:
        query = query.filter(AuditEvent.event_type == event_type)
    
    events = query.order_by(AuditEvent.created_at.desc()).limit(10000).all()  # Limit for safety
    
    if format == "json":
        return {
            "format": "json",
            "count": len(events),
            "events": [event.to_dict() for event in events]
        }
    elif format == "csv":
        # Convert to CSV format
        import csv
        import io
        
        output = io.StringIO()
        writer = csv.DictWriter(output, fieldnames=[
            'id', 'event_type', 'event_description', 'user_id', 'resource',
            'action', 'ip_address', 'user_agent', 'created_at'
        ])
        writer.writeheader()
        
        for event in events:
            writer.writerow({
                'id': str(event.id),
                'event_type': event.event_type,
                'event_description': event.event_description,
                'user_id': event.user_id,
                'resource': event.resource,
                'action': event.action,
                'ip_address': event.ip_address,
                'user_agent': event.user_agent,
                'created_at': event.created_at.isoformat() if event.created_at else None
            })
        
        return {
            "format": "csv",
            "count": len(events),
            "data": output.getvalue()
        }

if __name__ == "__main__":
    uvicorn.run(
        "main:app",
        host="0.0.0.0",
        port=settings.PORT,
        reload=settings.DEBUG,
        log_level=settings.LOG_LEVEL.lower()
    ) 
"""
Audit Service Utilities
Provides audit logging, compliance management, and security monitoring
"""

import json
import logging
from datetime import datetime, timedelta
from typing import Dict, Any, List, Optional

from sqlalchemy.orm import Session
from sqlalchemy import func
from sqlalchemy.types import Text

from models import AuditEvent, ComplianceReport, SecurityAlert

logger = logging.getLogger(__name__)


class AuditLogger:
    """Audit logging utilities"""
    
    @staticmethod
    def log_event(db: Session, event: AuditEvent):
        """Log an audit event to the database"""
        try:
            # Ensure event has required fields
            if not event.id:
                import uuid
                event.id = uuid.uuid4()
            
            if not event.created_at:
                event.created_at = datetime.utcnow()
            
            # Add to database
            db.add(event)
            db.commit()
            db.refresh(event)
            
            logger.info(f"Audit event logged: {event.event_type} - {event.event_description}")
            return event
            
        except Exception as e:
            logger.error(f"Failed to log audit event: {e}")
            db.rollback()
            raise
    
    @staticmethod
    def log_user_action(
        db: Session,
        user_id: str,
        action: str,
        resource: str,
        description: str,
        event_metadata: Optional[Dict[str, Any]] = None,
        ip_address: Optional[str] = None,
        user_agent: Optional[str] = None
    ):
        """Log a user action"""
        
        event = AuditEvent(
            event_type="user_action",
            event_description=description,
            user_id=user_id,
            resource=resource,
            action=action,
            event_metadata=event_metadata or {},
            ip_address=ip_address,
            user_agent=user_agent,
            security_relevant=action in ["delete", "modify", "access"],
            compliance_relevant=resource in ["user_data", "personal_info", "files"]
        )
        
        return AuditLogger.log_event(db, event)
    
    @staticmethod
    def log_system_event(
        db: Session,
        event_type: str,
        description: str,
        event_metadata: Optional[Dict[str, Any]] = None,
        risk_level: str = "low"
    ):
        """Log a system event"""
        
        event = AuditEvent(
            event_type=event_type,
            event_description=description,
            resource="system",
            action="system_event",
            event_metadata=event_metadata or {},
            risk_level=risk_level,
            security_relevant=risk_level in ["high", "critical"]
        )
        
        return AuditLogger.log_event(db, event)
    
    @staticmethod
    def log_security_event(
        db: Session,
        event_type: str,
        description: str,
        user_id: Optional[str] = None,
        ip_address: Optional[str] = None,
        event_metadata: Optional[Dict[str, Any]] = None,
        risk_level: str = "medium"
    ):
        """Log a security-related event"""
        
        event = AuditEvent(
            event_type=event_type,
            event_description=description,
            user_id=user_id,
            resource="security",
            action="security_event",
            ip_address=ip_address,
            event_metadata=event_metadata or {},
            security_relevant=True,
            risk_level=risk_level,
            tags=["security", "alert"]
        )
        
        return AuditLogger.log_event(db, event)


class ComplianceManager:
    """Compliance reporting and management"""
    
    @staticmethod
    def generate_report(
        db: Session,
        report_type: str,
        start_date: datetime,
        end_date: datetime
    ) -> Dict[str, Any]:
        """Generate a compliance report"""
        
        try:
            if report_type == "gdpr":
                return ComplianceManager._generate_gdpr_report(db, start_date, end_date)
            elif report_type == "ccpa":
                return ComplianceManager._generate_ccpa_report(db, start_date, end_date)
            elif report_type == "sox":
                return ComplianceManager._generate_sox_report(db, start_date, end_date)
            else:
                return ComplianceManager._generate_custom_report(db, start_date, end_date)
                
        except Exception as e:
            logger.error(f"Failed to generate {report_type} report: {e}")
            raise
    
    @staticmethod
    def _generate_gdpr_report(db: Session, start_date: datetime, end_date: datetime) -> Dict[str, Any]:
        """Generate GDPR compliance report"""
        
        # Data access events
        data_access = db.query(func.count(AuditEvent.id)).filter(
            AuditEvent.created_at.between(start_date, end_date),
            AuditEvent.event_type.in_(['data_access', 'file_downloaded', 'search_performed']),
            AuditEvent.compliance_relevant == True
        ).scalar() or 0
        
        # Data modification events
        data_modifications = db.query(func.count(AuditEvent.id)).filter(
            AuditEvent.created_at.between(start_date, end_date),
            AuditEvent.action.in_(['create', 'update', 'delete']),
            AuditEvent.compliance_relevant == True
        ).scalar() or 0
        
        # Data export events
        data_exports = db.query(func.count(AuditEvent.id)).filter(
            AuditEvent.created_at.between(start_date, end_date),
            AuditEvent.event_type == 'data_export'
        ).scalar() or 0
        
        # User consent events
        consent_events = db.query(func.count(AuditEvent.id)).filter(
            AuditEvent.created_at.between(start_date, end_date),
            AuditEvent.event_type.in_(['user_created', 'user_updated']),
            func.cast(AuditEvent.event_metadata, Text).ilike('%consent%')
        ).scalar() or 0
        
        return {
            "report_type": "gdpr",
            "period": {"start": start_date.isoformat(), "end": end_date.isoformat()},
            "summary": {
                "data_access_events": data_access,
                "data_modification_events": data_modifications,
                "data_export_events": data_exports,
                "consent_events": consent_events,
                "total_compliance_events": data_access + data_modifications + data_exports + consent_events
            },
            "compliance_status": "compliant" if data_exports == 0 or consent_events > 0 else "review_required",
            "recommendations": [
                "Ensure all data exports have proper authorization",
                "Maintain records of user consent",
                "Regular review of data access patterns"
            ]
        }
    
    @staticmethod
    def _generate_ccpa_report(db: Session, start_date: datetime, end_date: datetime) -> Dict[str, Any]:
        """Generate CCPA compliance report"""
        
        # Personal information access
        personal_access = db.query(func.count(AuditEvent.id)).filter(
            AuditEvent.created_at.between(start_date, end_date),
            AuditEvent.resource.in_(['user_data', 'personal_info']),
            AuditEvent.action == 'read'
        ).scalar() or 0
        
        # Data deletion requests
        deletion_requests = db.query(func.count(AuditEvent.id)).filter(
            AuditEvent.created_at.between(start_date, end_date),
            AuditEvent.event_type == 'user_deleted',
            func.cast(AuditEvent.event_metadata, Text).ilike('%ccpa%')
        ).scalar() or 0
        
        # Data portability requests
        portability_requests = db.query(func.count(AuditEvent.id)).filter(
            AuditEvent.created_at.between(start_date, end_date),
            AuditEvent.event_type == 'data_export',
            func.cast(AuditEvent.event_metadata, Text).ilike('%portability%')
        ).scalar() or 0
        
        return {
            "report_type": "ccpa",
            "period": {"start": start_date.isoformat(), "end": end_date.isoformat()},
            "summary": {
                "personal_info_access": personal_access,
                "deletion_requests": deletion_requests,
                "portability_requests": portability_requests,
                "total_privacy_events": personal_access + deletion_requests + portability_requests
            },
            "compliance_status": "compliant",
            "recommendations": [
                "Monitor personal information access patterns",
                "Ensure timely response to deletion requests",
                "Maintain audit trail for data portability"
            ]
        }
    
    @staticmethod
    def _generate_sox_report(db: Session, start_date: datetime, end_date: datetime) -> Dict[str, Any]:
        """Generate SOX compliance report"""
        
        # Financial data access
        financial_access = db.query(func.count(AuditEvent.id)).filter(
            AuditEvent.created_at.between(start_date, end_date),
            AuditEvent.resource.ilike('%financial%'),
            AuditEvent.action == 'read'
        ).scalar() or 0
        
        # Configuration changes
        config_changes = db.query(func.count(AuditEvent.id)).filter(
            AuditEvent.created_at.between(start_date, end_date),
            AuditEvent.event_type == 'config_changed'
        ).scalar() or 0
        
        # Administrative actions
        admin_actions = db.query(func.count(AuditEvent.id)).filter(
            AuditEvent.created_at.between(start_date, end_date),
            AuditEvent.resource == 'admin',
            AuditEvent.action.in_(['create', 'update', 'delete'])
        ).scalar() or 0
        
        return {
            "report_type": "sox",
            "period": {"start": start_date.isoformat(), "end": end_date.isoformat()},
            "summary": {
                "financial_data_access": financial_access,
                "configuration_changes": config_changes,
                "administrative_actions": admin_actions,
                "total_control_events": financial_access + config_changes + admin_actions
            },
            "compliance_status": "compliant",
            "recommendations": [
                "Regular review of financial data access",
                "Approval workflow for configuration changes",
                "Segregation of duties for administrative actions"
            ]
        }
    
    @staticmethod
    def _generate_custom_report(db: Session, start_date: datetime, end_date: datetime) -> Dict[str, Any]:
        """Generate custom compliance report"""
        
        # Total events
        total_events = db.query(func.count(AuditEvent.id)).filter(
            AuditEvent.created_at.between(start_date, end_date)
        ).scalar() or 0
        
        # Security events
        security_events = db.query(func.count(AuditEvent.id)).filter(
            AuditEvent.created_at.between(start_date, end_date),
            AuditEvent.security_relevant == True
        ).scalar() or 0
        
        # Compliance events
        compliance_events = db.query(func.count(AuditEvent.id)).filter(
            AuditEvent.created_at.between(start_date, end_date),
            AuditEvent.compliance_relevant == True
        ).scalar() or 0
        
        return {
            "report_type": "custom",
            "period": {"start": start_date.isoformat(), "end": end_date.isoformat()},
            "summary": {
                "total_events": total_events,
                "security_events": security_events,
                "compliance_events": compliance_events,
                "event_coverage": round((security_events + compliance_events) / max(total_events, 1) * 100, 2)
            },
            "compliance_status": "review_required",
            "recommendations": [
                "Review event categorization",
                "Enhance security monitoring",
                "Implement compliance tagging"
            ]
        }
    
    @staticmethod
    def get_compliance_summary(db: Session) -> Dict[str, Any]:
        """Get overall compliance summary"""
        
        # Last 30 days
        start_date = datetime.utcnow() - timedelta(days=30)
        
        total_events = db.query(func.count(AuditEvent.id)).filter(
            AuditEvent.created_at >= start_date
        ).scalar() or 0
        
        compliance_events = db.query(func.count(AuditEvent.id)).filter(
            AuditEvent.created_at >= start_date,
            AuditEvent.compliance_relevant == True
        ).scalar() or 0
        
        gdpr_events = db.query(func.count(AuditEvent.id)).filter(
            AuditEvent.created_at >= start_date,
            func.cast(AuditEvent.tags, Text).ilike('%gdpr%')
        ).scalar() or 0
        
        ccpa_events = db.query(func.count(AuditEvent.id)).filter(
            AuditEvent.created_at >= start_date,
            func.cast(AuditEvent.tags, Text).ilike('%ccpa%')
        ).scalar() or 0
        
        return {
            "period_days": 30,
            "total_events": total_events,
            "compliance_events": compliance_events,
            "gdpr_relevant": gdpr_events,
            "ccpa_relevant": ccpa_events,
            "data_access_events": compliance_events,
            "data_export_events": 0,  # Would need specific query
            "retention_compliance": {
                "policies_active": 1,
                "events_within_retention": total_events,
                "cleanup_required": False
            }
        }


class SecurityMonitor:
    """Security monitoring and alerting"""
    
    @staticmethod
    def start_monitoring():
        """Initialize security monitoring"""
        logger.info("Security monitoring initialized")
    
    @staticmethod
    def check_security_patterns(db: Session, event: AuditEvent):
        """Check for security patterns in audit events"""
        
        try:
            # Check for failed login patterns
            if event.event_type == "login_failed":
                SecurityMonitor._check_failed_login_pattern(db, event)
            
            # Check for suspicious activity
            if event.risk_level in ["high", "critical"]:
                SecurityMonitor._check_suspicious_activity(db, event)
            
            # Check for permission violations
            if event.event_type == "permission_denied":
                SecurityMonitor._check_permission_violations(db, event)
                
        except Exception as e:
            logger.error(f"Security pattern check failed: {e}")
    
    @staticmethod
    def _check_failed_login_pattern(db: Session, event: AuditEvent):
        """Check for failed login patterns"""
        
        if not event.ip_address:
            return
        
        # Count failed logins from same IP in last hour
        one_hour_ago = datetime.utcnow() - timedelta(hours=1)
        failed_count = db.query(func.count(AuditEvent.id)).filter(
            AuditEvent.created_at >= one_hour_ago,
            AuditEvent.event_type == "login_failed",
            AuditEvent.ip_address == event.ip_address
        ).scalar() or 0
        
        # Create alert if threshold exceeded
        if failed_count >= 5:
            SecurityMonitor._create_security_alert(
                db,
                "brute_force_attempt",
                "high",
                f"Multiple failed login attempts from IP {event.ip_address}",
                f"Detected {failed_count} failed login attempts from IP {event.ip_address} in the last hour",
                event.id,
                event.ip_address,
                event.user_id
            )
    
    @staticmethod
    def _check_suspicious_activity(db: Session, event: AuditEvent):
        """Check for suspicious activity patterns"""
        
        # High-risk events warrant immediate attention
        if event.risk_level == "critical":
            SecurityMonitor._create_security_alert(
                db,
                "critical_activity",
                "critical",
                f"Critical security event: {event.event_type}",
                event.event_description or "Critical security event detected",
                event.id,
                event.ip_address,
                event.user_id
            )
    
    @staticmethod
    def _check_permission_violations(db: Session, event: AuditEvent):
        """Check for permission violation patterns"""
        
        if not event.user_id:
            return
        
        # Count permission denials for user in last hour
        one_hour_ago = datetime.utcnow() - timedelta(hours=1)
        denial_count = db.query(func.count(AuditEvent.id)).filter(
            AuditEvent.created_at >= one_hour_ago,
            AuditEvent.event_type == "permission_denied",
            AuditEvent.user_id == event.user_id
        ).scalar() or 0
        
        # Create alert if threshold exceeded
        if denial_count >= 10:
            SecurityMonitor._create_security_alert(
                db,
                "permission_abuse",
                "medium",
                f"Multiple permission denials for user {event.user_id}",
                f"User {event.user_id} has been denied access {denial_count} times in the last hour",
                event.id,
                event.ip_address,
                event.user_id
            )
    
    @staticmethod
    def _create_security_alert(
        db: Session,
        alert_type: str,
        severity: str,
        title: str,
        description: str,
        source_event_id: Optional[str] = None,
        source_ip: Optional[str] = None,
        source_user_id: Optional[str] = None
    ):
        """Create a security alert"""
        
        try:
            alert = SecurityAlert(
                alert_type=alert_type,
                severity=severity,
                title=title,
                description=description,
                source_event_id=source_event_id,
                source_ip=source_ip,
                source_user_id=source_user_id,
                status="open"
            )
            
            db.add(alert)
            db.commit()
            
            logger.warning(f"Security alert created: {title}")
            
        except Exception as e:
            logger.error(f"Failed to create security alert: {e}")
            db.rollback()
    
    @staticmethod
    def calculate_security_score(
        failed_logins: int,
        permission_denials: int,
        suspicious_activities: int
    ) -> float:
        """Calculate security score based on events"""
        
        # Base score
        score = 100.0
        
        # Deduct points for security events
        score -= min(failed_logins * 2, 20)  # Max 20 points for failed logins
        score -= min(permission_denials * 1, 15)  # Max 15 points for permission denials
        score -= min(suspicious_activities * 5, 30)  # Max 30 points for suspicious activities
        
        return max(score, 0.0) 
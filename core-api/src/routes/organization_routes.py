"""
Organization Management Routes
Extracted from main.py for better code organization
Includes organization CRUD, domain management, member management, and invitations
"""

import uuid
import json
import logging
from datetime import datetime, timedelta
from typing import List, Optional
from fastapi import APIRouter, HTTPException, Depends
from sqlalchemy.orm import Session
from sqlalchemy import text

from models import (
    OrganizationCreate, OrganizationResponse, OrganizationMemberResponse,
    OrganizationDomainCreate, OrganizationDomainResponse, DomainTemplateResponse,
    InvitationCreate, InvitationResponse
)
from dependencies import get_db, get_current_user, require_permission
from auth_utils import PermissionManager, AuditLogger

# Initialize router
router = APIRouter(prefix="/organizations", tags=["organizations"])

logger = logging.getLogger(__name__)


# ============================================================================
# ORGANIZATION CRUD ENDPOINTS
# ============================================================================

@router.get("", response_model=List[OrganizationResponse])
async def list_organizations(
    current_user: dict = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """List organizations the user has access to"""
    result = db.execute(
        text("""
            SELECT DISTINCT o.id, o.name, o.slug, o.description, o.logo_url, o.website,
                   o.industry, o.size_category, o.subscription_tier, o.max_users,
                   o.max_storage_gb, o.max_domains, o.is_active, o.created_at,
                   (SELECT COUNT(*) FROM organization_members om WHERE om.organization_id = o.id AND om.is_active = true) as member_count,
                   (SELECT COUNT(*) FROM organization_domains od WHERE od.organization_id = o.id AND od.is_active = true) as domain_count
            FROM organizations o
            JOIN organization_members om ON o.id = om.organization_id
            WHERE om.user_id = :user_id AND om.is_active = true AND o.is_active = true
            ORDER BY o.name
        """),
        {"user_id": current_user["id"]}
    )
    
    return [
        OrganizationResponse(
            id=str(row.id),
            name=row.name,
            slug=row.slug,
            description=row.description,
            logo_url=row.logo_url,
            website=row.website,
            industry=row.industry,
            size_category=row.size_category,
            subscription_tier=row.subscription_tier,
            max_users=row.max_users,
            max_storage_gb=row.max_storage_gb,
            max_domains=row.max_domains,
            is_active=row.is_active,
            created_at=row.created_at.isoformat(),
            member_count=row.member_count,
            domain_count=row.domain_count
        )
        for row in result.fetchall()
    ]


@router.post("", response_model=OrganizationResponse)
async def create_organization(
    org_data: OrganizationCreate,
    current_user: dict = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Create a new organization"""
    try:
        # Check if slug is available
        existing = db.execute(
            text("SELECT id FROM organizations WHERE slug = :slug"),
            {"slug": org_data.slug}
        ).fetchone()
        
        if existing:
            raise HTTPException(status_code=400, detail="Organization slug already exists")
        
        # Set limits based on subscription tier
        tier_limits = {
            "basic": {"max_users": 10, "max_storage_gb": 10, "max_domains": 3},
            "professional": {"max_users": 50, "max_storage_gb": 100, "max_domains": 10},
            "enterprise": {"max_users": 1000, "max_storage_gb": 1000, "max_domains": 50}
        }
        limits = tier_limits.get(org_data.subscription_tier, tier_limits["basic"])
        
        # Create organization
        org_id = str(uuid.uuid4())
        db.execute(
            text("""
                INSERT INTO organizations (
                    id, name, slug, description, logo_url, website, industry,
                    size_category, subscription_tier, max_users, max_storage_gb, max_domains,
                    created_at
                ) VALUES (
                    :id, :name, :slug, :description, :logo_url, :website, :industry,
                    :size_category, :subscription_tier, :max_users, :max_storage_gb, :max_domains,
                    :created_at
                )
            """),
            {
                "id": org_id,
                "name": org_data.name,
                "slug": org_data.slug,
                "description": org_data.description,
                "logo_url": org_data.logo_url,
                "website": org_data.website,
                "industry": org_data.industry,
                "size_category": org_data.size_category,
                "subscription_tier": org_data.subscription_tier,
                "max_users": limits["max_users"],
                "max_storage_gb": limits["max_storage_gb"],
                "max_domains": limits["max_domains"],
                "created_at": datetime.utcnow()
            }
        )
        
        # Add creator as owner
        member_id = str(uuid.uuid4())
        db.execute(
            text("""
                INSERT INTO organization_members (id, organization_id, user_id, role, joined_at, is_active)
                VALUES (:id, :org_id, :user_id, 'owner', :joined_at, :is_active)
            """),
            {
                "id": member_id,
                "org_id": org_id,
                "user_id": current_user["id"],
                "joined_at": datetime.utcnow(),
                "is_active": True
            }
        )
        
        # Create default general domain
        domain_id = str(uuid.uuid4())
        db.execute(
            text("""
                INSERT INTO organization_domains (
                    id, organization_id, domain_name, display_name, description,
                    icon, color, created_by, is_active, created_at
                ) VALUES (
                    :id, :org_id, 'general', 'General', 'General knowledge and documentation',
                    'globe', 'blue', :created_by, :is_active, :created_at
                )
            """),
            {
                "id": domain_id,
                "org_id": org_id,
                "created_by": current_user["id"],
                "is_active": True,
                "created_at": datetime.utcnow()
            }
        )
        
        db.commit()
        
        # Log organization creation
        AuditLogger.log_event(
            db, "organization_creation", current_user["id"], "organizations", "create",
            f"Created organization {org_data.name}",
            {"organization_id": org_id, "slug": org_data.slug}
        )
        
        return OrganizationResponse(
            id=org_id,
            name=org_data.name,
            slug=org_data.slug,
            description=org_data.description,
            logo_url=org_data.logo_url,
            website=org_data.website,
            industry=org_data.industry,
            size_category=org_data.size_category,
            subscription_tier=org_data.subscription_tier,
            max_users=limits["max_users"],
            max_storage_gb=limits["max_storage_gb"],
            max_domains=limits["max_domains"],
            is_active=True,
            created_at=datetime.utcnow().isoformat(),
            member_count=1,
            domain_count=1
        )
        
    except HTTPException:
        raise
    except Exception as e:
        db.rollback()
        raise HTTPException(status_code=500, detail=f"Failed to create organization: {str(e)}")


# ============================================================================
# DOMAIN MANAGEMENT ENDPOINTS
# ============================================================================

@router.get("/{org_id}/domains", response_model=List[OrganizationDomainResponse])
async def list_organization_domains(
    org_id: str,
    current_user: dict = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """List domains for an organization"""
    # Check if user has access to this organization
    member = db.execute(
        text("""
            SELECT role FROM organization_members 
            WHERE organization_id = :org_id AND user_id = :user_id AND is_active = true
        """),
        {"org_id": org_id, "user_id": current_user["id"]}
    ).fetchone()
    
    if not member:
        raise HTTPException(status_code=403, detail="Access denied to organization")
    
    result = db.execute(
        text("""
            SELECT id, organization_id, domain_name, display_name, description,
                   icon, color, settings, created_by, is_active, created_at
            FROM organization_domains
            WHERE organization_id = :org_id AND is_active = true
            ORDER BY domain_name
        """),
        {"org_id": org_id}
    )
    
    return [
        OrganizationDomainResponse(
            id=str(row.id),
            organization_id=str(row.organization_id),
            domain_name=row.domain_name,
            display_name=row.display_name,
            description=row.description,
            icon=row.icon,
            color=row.color,
            settings=json.loads(row.settings) if row.settings else {},
            created_by=str(row.created_by) if row.created_by else None,
            is_active=row.is_active,
            created_at=row.created_at.isoformat()
        )
        for row in result.fetchall()
    ]


@router.post("/{org_id}/domains", response_model=OrganizationDomainResponse)
async def create_organization_domain(
    org_id: str,
    domain_data: OrganizationDomainCreate,
    current_user: dict = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Create a new domain for an organization"""
    try:
        # Check if user has admin access to this organization
        member = db.execute(
            text("""
                SELECT role FROM organization_members 
                WHERE organization_id = :org_id AND user_id = :user_id AND is_active = true
            """),
            {"org_id": org_id, "user_id": current_user["id"]}
        ).fetchone()
        
        if not member or member.role not in ['owner', 'admin']:
            raise HTTPException(status_code=403, detail="Admin access required")
        
        # Check domain limits
        org_info = db.execute(
            text("SELECT max_domains FROM organizations WHERE id = :org_id"),
            {"org_id": org_id}
        ).fetchone()
        
        current_domains = db.execute(
            text("SELECT COUNT(*) as count FROM organization_domains WHERE organization_id = :org_id AND is_active = true"),
            {"org_id": org_id}
        ).fetchone()
        
        if current_domains.count >= org_info.max_domains:
            raise HTTPException(status_code=400, detail="Domain limit reached for this organization")
        
        # Check if domain name is unique within organization
        existing = db.execute(
            text("SELECT id FROM organization_domains WHERE organization_id = :org_id AND domain_name = :domain_name"),
            {"org_id": org_id, "domain_name": domain_data.domain_name}
        ).fetchone()
        
        if existing:
            raise HTTPException(status_code=400, detail="Domain name already exists in this organization")
        
        # Get template settings if template_id provided
        settings = domain_data.settings
        if domain_data.template_id:
            template = db.execute(
                text("SELECT suggested_settings FROM domain_templates WHERE id = :template_id"),
                {"template_id": domain_data.template_id}
            ).fetchone()
            if template:
                settings.update(template.suggested_settings or {})
        
        # Create domain
        domain_id = str(uuid.uuid4())
        db.execute(
            text("""
                INSERT INTO organization_domains (
                    id, organization_id, domain_name, display_name, description,
                    icon, color, settings, created_by, created_at
                ) VALUES (
                    :id, :org_id, :domain_name, :display_name, :description,
                    :icon, :color, :settings, :created_by, :created_at
                )
            """),
            {
                "id": domain_id,
                "org_id": org_id,
                "domain_name": domain_data.domain_name,
                "display_name": domain_data.display_name,
                "description": domain_data.description,
                "icon": domain_data.icon,
                "color": domain_data.color,
                "settings": json.dumps(settings),
                "created_by": current_user["id"],
                "created_at": datetime.utcnow()
            }
        )
        
        db.commit()
        
        # Log domain creation
        AuditLogger.log_event(
            db, "domain_creation", current_user["id"], "organization_domains", "create",
            f"Created domain {domain_data.domain_name} in organization {org_id}",
            {"domain_id": domain_id, "domain_name": domain_data.domain_name}
        )
        
        return OrganizationDomainResponse(
            id=domain_id,
            organization_id=org_id,
            domain_name=domain_data.domain_name,
            display_name=domain_data.display_name,
            description=domain_data.description,
            icon=domain_data.icon,
            color=domain_data.color,
            settings=settings,
            created_by=current_user["id"],
            is_active=True,
            created_at=datetime.utcnow().isoformat()
        )
        
    except HTTPException:
        raise
    except Exception as e:
        db.rollback()
        raise HTTPException(status_code=500, detail=f"Failed to create domain: {str(e)}")


# ============================================================================
# MEMBER MANAGEMENT ENDPOINTS
# ============================================================================

@router.get("/{org_id}/members", response_model=List[OrganizationMemberResponse])
async def list_organization_members(
    org_id: str,
    current_user: dict = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """List members of an organization"""
    # Check if user has access to this organization
    member = db.execute(
        text("""
            SELECT role FROM organization_members 
            WHERE organization_id = :org_id AND user_id = :user_id AND is_active = true
        """),
        {"org_id": org_id, "user_id": current_user["id"]}
    ).fetchone()
    
    if not member:
        raise HTTPException(status_code=403, detail="Access denied to organization")
    
    result = db.execute(
        text("""
            SELECT om.id, om.user_id, u.username, u.email, u.full_name, om.role,
                   om.joined_at, u.last_login, om.is_active
            FROM organization_members om
            JOIN users u ON om.user_id = u.id
            WHERE om.organization_id = :org_id AND om.is_active = true
            ORDER BY om.role, u.username
        """),
        {"org_id": org_id}
    )
    
    members = []
    for row in result.fetchall():
        # Get user permissions
        permissions = PermissionManager.get_user_permissions(db, str(row.user_id))
        
        members.append(OrganizationMemberResponse(
            id=str(row.id),
            user_id=str(row.user_id),
            username=row.username,
            email=row.email,
            full_name=row.full_name,
            role=row.role,
            permissions=permissions,
            joined_at=row.joined_at.isoformat(),
            last_active=row.last_login.isoformat() if row.last_login else None,
            is_active=row.is_active
        ))
    
    return members


@router.post("/{org_id}/members/invite", response_model=InvitationResponse)
async def invite_organization_member(
    org_id: str,
    invitation_data: InvitationCreate,
    current_user: dict = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Invite a new member to the organization"""
    try:
        # Check if user has admin access to this organization
        member = db.execute(
            text("""
                SELECT role FROM organization_members 
                WHERE organization_id = :org_id AND user_id = :user_id AND is_active = true
            """),
            {"org_id": org_id, "user_id": current_user["id"]}
        ).fetchone()
        
        if not member or member.role not in ['owner', 'admin']:
            raise HTTPException(status_code=403, detail="Admin access required")
        
        # Check if user is already a member
        existing_member = db.execute(
            text("""
                SELECT om.id FROM organization_members om
                JOIN users u ON om.user_id = u.id
                WHERE om.organization_id = :org_id AND u.email = :email AND om.is_active = true
            """),
            {"org_id": org_id, "email": invitation_data.email}
        ).fetchone()
        
        if existing_member:
            raise HTTPException(status_code=400, detail="User is already a member of this organization")
        
        # Check if there's already a pending invitation
        existing_invitation = db.execute(
            text("""
                SELECT id FROM organization_invitations 
                WHERE organization_id = :org_id AND email = :email AND expires_at > :now
            """),
            {"org_id": org_id, "email": invitation_data.email, "now": datetime.utcnow()}
        ).fetchone()
        
        if existing_invitation:
            raise HTTPException(status_code=400, detail="Invitation already sent to this email")
        
        # Check member limits
        org_info = db.execute(
            text("SELECT max_users FROM organizations WHERE id = :org_id"),
            {"org_id": org_id}
        ).fetchone()
        
        current_members = db.execute(
            text("SELECT COUNT(*) as count FROM organization_members WHERE organization_id = :org_id AND is_active = true"),
            {"org_id": org_id}
        ).fetchone()
        
        if current_members.count >= org_info.max_users:
            raise HTTPException(status_code=400, detail="Member limit reached for this organization")
        
        # Generate invitation token
        invitation_token = str(uuid.uuid4())
        invitation_id = str(uuid.uuid4())
        expires_at = datetime.utcnow() + timedelta(days=7)  # 7 days to accept
        
        # Create invitation
        db.execute(
            text("""
                INSERT INTO organization_invitations (
                    id, organization_id, email, role, invited_by, invitation_token,
                    expires_at, created_at
                ) VALUES (
                    :id, :org_id, :email, :role, :invited_by, :token,
                    :expires_at, :created_at
                )
            """),
            {
                "id": invitation_id,
                "org_id": org_id,
                "email": invitation_data.email,
                "role": invitation_data.role,
                "invited_by": current_user["id"],
                "token": invitation_token,
                "expires_at": expires_at,
                "created_at": datetime.utcnow()
            }
        )
        
        db.commit()
        
        # Log invitation
        AuditLogger.log_event(
            db, "member_invitation", current_user["id"], "organization_invitations", "create",
            f"Invited {invitation_data.email} to organization {org_id}",
            {"invitation_id": invitation_id, "email": invitation_data.email, "role": invitation_data.role}
        )
        
        # TODO: Send invitation email
        
        return InvitationResponse(
            id=invitation_id,
            organization_id=org_id,
            email=invitation_data.email,
            role=invitation_data.role,
            invited_by=current_user["id"],
            invitation_token=invitation_token,
            expires_at=expires_at.isoformat(),
            created_at=datetime.utcnow().isoformat()
        )
        
    except HTTPException:
        raise
    except Exception as e:
        db.rollback()
        raise HTTPException(status_code=500, detail=f"Failed to send invitation: {str(e)}")


@router.put("/{org_id}/members/{member_id}", response_model=OrganizationMemberResponse)
async def update_organization_member(
    org_id: str,
    member_id: str,
    role: str,
    current_user: dict = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Update organization member role"""
    try:
        # Check if user has admin access to this organization
        admin_member = db.execute(
            text("""
                SELECT role FROM organization_members 
                WHERE organization_id = :org_id AND user_id = :user_id AND is_active = true
            """),
            {"org_id": org_id, "user_id": current_user["id"]}
        ).fetchone()
        
        if not admin_member or admin_member.role not in ['owner', 'admin']:
            raise HTTPException(status_code=403, detail="Admin access required")
        
        # Get member to update
        member = db.execute(
            text("""
                SELECT om.id, om.user_id, om.role, u.username, u.email, u.full_name, om.joined_at
                FROM organization_members om
                JOIN users u ON om.user_id = u.id
                WHERE om.id = :member_id AND om.organization_id = :org_id AND om.is_active = true
            """),
            {"member_id": member_id, "org_id": org_id}
        ).fetchone()
        
        if not member:
            raise HTTPException(status_code=404, detail="Member not found")
        
        # Prevent changing owner role unless you are the owner
        if member.role == 'owner' and admin_member.role != 'owner':
            raise HTTPException(status_code=403, detail="Only owner can change owner role")
        
        # Update member role
        db.execute(
            text("""
                UPDATE organization_members 
                SET role = :role, updated_at = :updated_at
                WHERE id = :member_id
            """),
            {
                "role": role,
                "updated_at": datetime.utcnow(),
                "member_id": member_id
            }
        )
        
        db.commit()
        
        # Get updated permissions
        permissions = PermissionManager.get_user_permissions(db, str(member.user_id))
        
        # Log role change
        AuditLogger.log_event(
            db, "member_role_update", current_user["id"], "organization_members", "update",
            f"Updated role for {member.email} from {member.role} to {role}",
            {"member_id": member_id, "old_role": member.role, "new_role": role}
        )
        
        return OrganizationMemberResponse(
            id=str(member.id),
            user_id=str(member.user_id),
            username=member.username,
            email=member.email,
            full_name=member.full_name,
            role=role,
            permissions=permissions,
            joined_at=member.joined_at.isoformat(),
            last_active=None,  # Would need to join with users table for last_login
            is_active=True
        )
        
    except HTTPException:
        raise
    except Exception as e:
        db.rollback()
        raise HTTPException(status_code=500, detail=f"Failed to update member: {str(e)}")


@router.delete("/{org_id}/members/{member_id}")
async def remove_organization_member(
    org_id: str,
    member_id: str,
    current_user: dict = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Remove member from organization"""
    try:
        # Check if user has admin access to this organization
        admin_member = db.execute(
            text("""
                SELECT role FROM organization_members 
                WHERE organization_id = :org_id AND user_id = :user_id AND is_active = true
            """),
            {"org_id": org_id, "user_id": current_user["id"]}
        ).fetchone()
        
        if not admin_member or admin_member.role not in ['owner', 'admin']:
            raise HTTPException(status_code=403, detail="Admin access required")
        
        # Get member to remove
        member = db.execute(
            text("""
                SELECT om.id, om.user_id, om.role, u.email
                FROM organization_members om
                JOIN users u ON om.user_id = u.id
                WHERE om.id = :member_id AND om.organization_id = :org_id AND om.is_active = true
            """),
            {"member_id": member_id, "org_id": org_id}
        ).fetchone()
        
        if not member:
            raise HTTPException(status_code=404, detail="Member not found")
        
        # Prevent removing owner unless you are the owner
        if member.role == 'owner' and admin_member.role != 'owner':
            raise HTTPException(status_code=403, detail="Only owner can remove owner")
        
        # Prevent removing yourself if you're the only owner
        if member.user_id == current_user["id"] and member.role == 'owner':
            owner_count = db.execute(
                text("""
                    SELECT COUNT(*) as count FROM organization_members 
                    WHERE organization_id = :org_id AND role = 'owner' AND is_active = true
                """),
                {"org_id": org_id}
            ).fetchone()
            
            if owner_count.count <= 1:
                raise HTTPException(status_code=400, detail="Cannot remove the only owner")
        
        # Deactivate member instead of deleting
        db.execute(
            text("""
                UPDATE organization_members 
                SET is_active = false, updated_at = :updated_at
                WHERE id = :member_id
            """),
            {
                "updated_at": datetime.utcnow(),
                "member_id": member_id
            }
        )
        
        db.commit()
        
        # Log member removal
        AuditLogger.log_event(
            db, "member_removal", current_user["id"], "organization_members", "delete",
            f"Removed member {member.email} from organization",
            {"member_id": member_id, "removed_user_id": str(member.user_id)}
        )
        
        return {"message": "Member removed successfully"}
        
    except HTTPException:
        raise
    except Exception as e:
        db.rollback()
        raise HTTPException(status_code=500, detail=f"Failed to remove member: {str(e)}")


# ============================================================================
# DOMAIN TEMPLATES
# ============================================================================

# Create a separate router for domain templates
templates_router = APIRouter(prefix="/domain-templates", tags=["domain-templates"])


@templates_router.get("", response_model=List[DomainTemplateResponse])
async def list_domain_templates(
    category: Optional[str] = None,
    current_user: dict = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """List available domain templates"""
    where_clause = "WHERE is_active = true"
    params = {}
    
    if category:
        where_clause += " AND category = :category"
        params["category"] = category
    
    result = db.execute(
        text(f"""
            SELECT id, name, display_name, description, icon, color, category, suggested_settings
            FROM domain_templates
            {where_clause}
            ORDER BY category, display_name
        """),
        params
    )
    
    return [
        DomainTemplateResponse(
            id=str(row.id),
            name=row.name,
            display_name=row.display_name,
            description=row.description,
            icon=row.icon,
            color=row.color,
            category=row.category,
            suggested_settings=row.suggested_settings or {}
        )
        for row in result.fetchall()
    ]


# Export all routers
__all__ = ["router", "templates_router"] 
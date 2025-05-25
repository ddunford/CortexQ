"""
User Profile Management Routes
Extracted from main.py for better code organization
Includes user profile updates and password management
"""

from datetime import datetime
from fastapi import APIRouter, HTTPException, Depends
from sqlalchemy.orm import Session
from sqlalchemy import text

from models import UserResponse
from dependencies import get_db, get_current_user
from auth_utils import AuthUtils, PermissionManager, AuditLogger

# Initialize router
router = APIRouter(prefix="/users", tags=["user-profile"])


@router.put("/me", response_model=UserResponse)
async def update_user_profile(
    profile_data: dict,
    current_user: dict = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Update current user's profile"""
    try:
        # Build update query dynamically based on provided fields
        update_fields = []
        params = {"user_id": current_user["id"], "updated_at": datetime.utcnow()}
        
        if "full_name" in profile_data:
            update_fields.append("full_name = :full_name")
            params["full_name"] = profile_data["full_name"]
        
        if "email" in profile_data:
            # Check if email is already taken
            existing = db.execute(
                text("SELECT id FROM users WHERE email = :email AND id != :user_id"),
                {"email": profile_data["email"], "user_id": current_user["id"]}
            ).fetchone()
            if existing:
                raise HTTPException(status_code=400, detail="Email already in use")
            
            update_fields.append("email = :email")
            params["email"] = profile_data["email"]
        
        if update_fields:
            update_query = f"""
                UPDATE users 
                SET {', '.join(update_fields)}, updated_at = :updated_at
                WHERE id = :user_id
            """
            db.execute(text(update_query), params)
            db.commit()
        
        # Get updated user data
        user_result = db.execute(
            text("""
                SELECT id, username, email, full_name, is_active, created_at
                FROM users WHERE id = :user_id
            """),
            {"user_id": current_user["id"]}
        ).fetchone()
        
        roles = PermissionManager.get_user_roles(db, current_user["id"])
        permissions = PermissionManager.get_user_permissions(db, current_user["id"])
        domains = PermissionManager.get_user_domains(db, current_user["id"])
        
        # Log profile update
        AuditLogger.log_event(
            db, "profile_update", current_user["id"], "users", "update",
            f"Updated profile for {user_result.email}",
            {"updated_fields": list(profile_data.keys())}
        )
        
        return UserResponse(
            id=str(user_result.id),
            username=user_result.username,
            email=user_result.email,
            full_name=user_result.full_name,
            is_active=user_result.is_active,
            roles=roles,
            permissions=permissions,
            domains=domains
        )
        
    except HTTPException:
        raise
    except Exception as e:
        db.rollback()
        raise HTTPException(status_code=500, detail=f"Failed to update profile: {str(e)}")


@router.put("/me/password")
async def change_user_password(
    password_data: dict,
    current_user: dict = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Change current user's password"""
    try:
        current_password = password_data.get("current_password")
        new_password = password_data.get("new_password")
        
        if not current_password or not new_password:
            raise HTTPException(status_code=400, detail="Current and new passwords are required")
        
        # Get current password hash
        user_result = db.execute(
            text("SELECT password_hash FROM users WHERE id = :user_id"),
            {"user_id": current_user["id"]}
        ).fetchone()
        
        # Verify current password
        if not AuthUtils.verify_password(current_password, user_result.password_hash):
            raise HTTPException(status_code=400, detail="Current password is incorrect")
        
        # Hash new password
        new_password_hash = AuthUtils.hash_password(new_password)
        
        # Update password
        db.execute(
            text("""
                UPDATE users 
                SET password_hash = :password_hash, updated_at = :updated_at
                WHERE id = :user_id
            """),
            {
                "password_hash": new_password_hash,
                "updated_at": datetime.utcnow(),
                "user_id": current_user["id"]
            }
        )
        
        db.commit()
        
        # Log password change
        AuditLogger.log_event(
            db, "password_change", current_user["id"], "users", "update",
            f"Password changed for user {current_user['email']}",
            {}
        )
        
        return {"message": "Password updated successfully"}
        
    except HTTPException:
        raise
    except Exception as e:
        db.rollback()
        raise HTTPException(status_code=500, detail=f"Failed to change password: {str(e)}")


# Export router
__all__ = ["router"] 
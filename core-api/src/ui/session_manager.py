"""
Session Manager for Chat API Service
Handles chat sessions, message history, and user context tracking.
"""

import uuid
from datetime import datetime, timedelta
from typing import List, Optional, Dict, Any

from sqlalchemy.orm import Session
from sqlalchemy import desc

from database import ChatSession, ChatMessage, User
from config import get_settings

settings = get_settings()


class SessionManager:
    """Manages chat sessions and message history"""
    
    def __init__(self):
        self.active_sessions = {}  # In-memory tracking for WebSocket connections
    
    def get_or_create_session(self, session_id: str, user_id: str, domain: str, db: Session) -> ChatSession:
        """Get existing session or create new one"""
        # Try to find existing session
        session = db.query(ChatSession).filter(
            ChatSession.session_id == session_id,
            ChatSession.is_active == True
        ).first()
        
        if session:
            # Update last activity
            session.last_activity = datetime.utcnow()
            session.domain = domain  # Update domain if changed
            db.commit()
            return session
        
        # Create new session
        session = ChatSession(
            session_id=session_id,
            user_id=uuid.UUID(user_id),
            domain=domain,
            context={
                "created_via": "api",
                "initial_domain": domain
            }
        )
        
        db.add(session)
        db.commit()
        db.refresh(session)
        
        return session
    
    def get_session(self, session_id: str, db: Session) -> Optional[ChatSession]:
        """Get session by ID"""
        return db.query(ChatSession).filter(
            ChatSession.session_id == session_id,
            ChatSession.is_active == True
        ).first()
    
    def add_message(self, session_id: str, message_type: str, content: str, 
                   metadata: Optional[Dict[str, Any]], db: Session) -> ChatMessage:
        """Add message to session"""
        session = db.query(ChatSession).filter(
            ChatSession.session_id == session_id
        ).first()
        
        if not session:
            raise ValueError(f"Session {session_id} not found")
        
        # Create message
        message = ChatMessage(
            session_id=session.id,
            message_type=message_type,
            content=content,
            message_metadata=metadata or {}
        )
        
        db.add(message)
        
        # Update session
        session.message_count += 1
        session.last_activity = datetime.utcnow()
        
        db.commit()
        db.refresh(message)
        
        return message
    
    def get_session_messages(self, session_id: str, db: Session, limit: int = 50, 
                           offset: int = 0) -> List[Dict[str, Any]]:
        """Get messages for a session with pagination"""
        session = db.query(ChatSession).filter(
            ChatSession.session_id == session_id
        ).first()
        
        if not session:
            return []
        
        messages = db.query(ChatMessage).filter(
            ChatMessage.session_id == session.id
        ).order_by(desc(ChatMessage.created_at)).offset(offset).limit(limit).all()
        
        return [
            {
                "id": str(msg.id),
                "type": msg.message_type,
                "content": msg.content,
                "metadata": msg.message_metadata,
                "created_at": msg.created_at.isoformat()
            }
            for msg in reversed(messages)  # Reverse to get chronological order
        ]
    
    def get_recent_context(self, session_id: str, db: Session, 
                          message_count: Optional[int] = None) -> List[Dict[str, Any]]:
        """Get recent messages for context"""
        if message_count is None:
            message_count = settings.MAX_CONTEXT_MESSAGES
        
        session = db.query(ChatSession).filter(
            ChatSession.session_id == session_id
        ).first()
        
        if not session:
            return []
        
        messages = db.query(ChatMessage).filter(
            ChatMessage.session_id == session.id
        ).order_by(desc(ChatMessage.created_at)).limit(message_count).all()
        
        return [
            {
                "role": "user" if msg.message_type == "user" else "assistant",
                "content": msg.content,
                "timestamp": msg.created_at.isoformat()
            }
            for msg in reversed(messages)
        ]
    
    def update_session_activity(self, session_id: str, db: Session):
        """Update session last activity timestamp"""
        session = db.query(ChatSession).filter(
            ChatSession.session_id == session_id
        ).first()
        
        if session:
            session.last_activity = datetime.utcnow()
            db.commit()
    
    def get_user_sessions(self, user_id: str, db: Session) -> List[ChatSession]:
        """Get all active sessions for a user"""
        return db.query(ChatSession).filter(
            ChatSession.user_id == uuid.UUID(user_id),
            ChatSession.is_active == True
        ).order_by(desc(ChatSession.last_activity)).all()
    
    def delete_session(self, session_id: str, db: Session) -> bool:
        """Soft delete a session"""
        session = db.query(ChatSession).filter(
            ChatSession.session_id == session_id
        ).first()
        
        if not session:
            return False
        
        session.is_active = False
        session.ended_at = datetime.utcnow()
        db.commit()
        
        return True
    
    def cleanup_expired_sessions(self, db: Session):
        """Clean up expired sessions"""
        expiry_time = datetime.utcnow() - timedelta(hours=settings.MAX_SESSION_DURATION_HOURS)
        
        expired_sessions = db.query(ChatSession).filter(
            ChatSession.last_activity < expiry_time,
            ChatSession.is_active == True
        ).all()
        
        for session in expired_sessions:
            session.is_active = False
            session.ended_at = datetime.utcnow()
        
        db.commit()
        
        return len(expired_sessions)
    
    def get_active_session_count(self) -> int:
        """Get count of active WebSocket sessions"""
        return len(self.active_sessions)
    
    def add_websocket_session(self, session_id: str, websocket):
        """Track WebSocket connection"""
        self.active_sessions[session_id] = {
            "websocket": websocket,
            "connected_at": datetime.utcnow()
        }
    
    def remove_websocket_session(self, session_id: str):
        """Remove WebSocket connection tracking"""
        self.active_sessions.pop(session_id, None)
    
    def update_session_title(self, session_id: str, title: str, db: Session) -> bool:
        """Update session title"""
        session = db.query(ChatSession).filter(
            ChatSession.session_id == session_id
        ).first()
        
        if not session:
            return False
        
        session.title = title[:255]  # Truncate if too long
        db.commit()
        
        return True
    
    def update_session_context(self, session_id: str, context_update: Dict[str, Any], db: Session) -> bool:
        """Update session context"""
        session = db.query(ChatSession).filter(
            ChatSession.session_id == session_id
        ).first()
        
        if not session:
            return False
        
        # Merge context
        current_context = session.context or {}
        current_context.update(context_update)
        session.context = current_context
        
        db.commit()
        
        return True 
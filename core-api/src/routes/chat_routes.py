"""
Chat and RAG Processing Routes
Extracted from main.py for better code organization
"""

import uuid
import json
import logging
from datetime import datetime
from fastapi import APIRouter, HTTPException, Depends
from sqlalchemy.orm import Session
from sqlalchemy import text

import sys
import os
# Add the parent directory to the path
parent_dir = os.path.dirname(os.path.dirname(__file__))
sys.path.insert(0, parent_dir)

from models import ChatRequest, ChatResponse
from dependencies import get_db, get_current_user, require_permission
from auth_utils import PermissionManager, AuditLogger
from rag_processor import RAGRequest

# Initialize router
router = APIRouter(tags=["chat"])

# Initialize RAG processor (will be set by main app)
rag_processor = None

logger = logging.getLogger(__name__)


def set_rag_processor(processor):
    """Set the RAG processor instance"""
    global rag_processor
    rag_processor = processor


# ============================================================================
# CHAT ENDPOINTS
# ============================================================================

@router.post("", response_model=ChatResponse)
async def chat(
    request: ChatRequest,
    current_user: dict = Depends(require_permission("chat:write")),
    db: Session = Depends(get_db)
):
    """Enhanced chat with intent classification and RAG"""
    try:
        # Check domain access
        if not PermissionManager.has_domain_access(db, current_user["id"], request.domain):
            raise HTTPException(
                status_code=403,
                detail=f"Access denied to domain: {request.domain}"
            )
        
        # Create session if not provided
        session_id = request.session_id or str(uuid.uuid4())
        
        # Get user's organization for multi-tenant isolation
        org_result = db.execute(
            text("""
                SELECT om.organization_id
                FROM organization_members om
                WHERE om.user_id = :user_id AND om.is_active = true
                LIMIT 1
            """),
            {"user_id": current_user["id"]}
        ).fetchone()
        
        if not org_result:
            raise HTTPException(status_code=403, detail="User not associated with any organization")
        
        organization_id = str(org_result.organization_id)

        # Ensure chat session exists
        db.execute(
            text("""
                INSERT INTO chat_sessions (id, session_id, user_id, organization_id, domain, created_at)
                VALUES (:id, :session_id, :user_id, :organization_id, :domain, :created_at)
                ON CONFLICT (session_id) DO NOTHING
            """),
            {
                "id": str(uuid.uuid4()),
                "session_id": session_id,
                "user_id": current_user["id"],
                "organization_id": organization_id,
                "domain": request.domain,
                "created_at": datetime.utcnow()
            }
        )
        
        # Get conversation context
        context_result = db.execute(
            text("""
                SELECT cm.content, cm.message_type, cm.created_at
                FROM chat_messages cm
                JOIN chat_sessions cs ON cm.session_id = cs.id
                WHERE cs.session_id = :session_id
                ORDER BY cm.created_at DESC
                LIMIT 5
            """),
            {"session_id": session_id}
        )
        
        recent_messages = [
            {
                "content": row.content,
                "type": row.message_type,
                "timestamp": row.created_at.isoformat()
            }
            for row in context_result.fetchall()
        ]
        
        # Create RAG request with organization context
        rag_request = RAGRequest(
            query=request.message,
            domain=request.domain,
            mode=request.mode,
            max_results=request.max_results,
            confidence_threshold=request.confidence_threshold,
            context={"recent_messages": recent_messages},
            user_id=current_user["id"],
            session_id=session_id,
            organization_id=organization_id
        )
        
        # Process with RAG
        if not rag_processor:
            raise HTTPException(status_code=503, detail="RAG processor not available")
        
        rag_response = await rag_processor.process_query(rag_request, db)
        
        # Get session record
        session_result = db.execute(
            text("SELECT id FROM chat_sessions WHERE session_id = :session_id"),
            {"session_id": session_id}
        )
        session_record = session_result.fetchone()
        
        if session_record:
            # Store user message
            db.execute(
                text("""
                    INSERT INTO chat_messages (id, session_id, organization_id, message_type, content, created_at)
                    VALUES (:id, :session_id, :organization_id, :message_type, :content, :created_at)
                """),
                {
                    "id": str(uuid.uuid4()),
                    "session_id": session_record.id,
                    "organization_id": organization_id,
                    "message_type": "user",
                    "content": request.message,
                    "created_at": datetime.utcnow()
                }
            )
            
            # Store assistant response
            db.execute(
                text("""
                    INSERT INTO chat_messages (id, session_id, organization_id, message_type, content, intent, confidence, sources, created_at)
                    VALUES (:id, :session_id, :organization_id, :message_type, :content, :intent, :confidence, :sources, :created_at)
                """),
                {
                    "id": str(uuid.uuid4()),
                    "session_id": session_record.id,
                    "organization_id": organization_id,
                    "message_type": "assistant",
                    "content": rag_response.response,
                    "intent": rag_response.intent,
                    "confidence": rag_response.confidence,
                    "sources": json.dumps(rag_response.sources),
                    "created_at": datetime.utcnow()
                }
            )
        
        db.commit()
        
        # Log chat interaction
        AuditLogger.log_event(
            db, "chat_interaction", current_user["id"], "chat", "query",
            f"Chat query in domain {request.domain}",
            {
                "query_length": len(request.message),
                "intent": rag_response.intent,
                "confidence": rag_response.confidence,
                "domain": request.domain
            }
        )
        
        return ChatResponse(
            response=rag_response.response,
            intent=rag_response.intent,
            confidence=rag_response.confidence,
            sources=rag_response.sources,
            session_id=session_id,
            processing_time_ms=rag_response.processing_time_ms,
            mode_used=rag_response.mode_used,
            response_type=rag_response.response_type,
            source_count=len(rag_response.sources),
            suggested_actions=rag_response.suggested_actions,
            related_queries=rag_response.related_queries,
            agent_workflow_triggered=rag_response.agent_workflow_triggered,
            agent_workflow_id=rag_response.agent_workflow_id,
            execution_id=rag_response.execution_id
        )
        
    except HTTPException:
        raise
    except Exception as e:
        db.rollback()
        raise HTTPException(status_code=500, detail=f"Chat failed: {str(e)}")


# Export router
__all__ = ["router"] 
"""
Chat API Service - Multi-Domain RAG Interface
Provides real-time chat interface with WebSocket support and domain-aware conversations.
"""

import os
import uuid
import asyncio
import json
from typing import List, Optional, Dict, Any
from datetime import datetime

import uvicorn
import httpx
from fastapi import FastAPI, WebSocket, WebSocketDisconnect, HTTPException, Depends, Query, Body
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import HTMLResponse
from pydantic import BaseModel
from sqlalchemy.orm import Session

from config import get_settings
from database import get_db, ChatSession, ChatMessage, User
from session_manager import SessionManager
from domain_client import DomainVectorClient
from message_processor import MessageProcessor

# Initialize FastAPI app
app = FastAPI(
    title="Multi-Domain Chat API",
    description="Real-time chat interface for multi-domain RAG system",
    version="0.1.0"
)

# Global instances
settings = get_settings()
session_manager = SessionManager()
domain_client = DomainVectorClient(settings.VECTOR_SERVICE_URL)
message_processor = MessageProcessor(domain_client, settings)

# Add CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins_list,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Request/Response Models
class ChatRequest(BaseModel):
    message: str
    domain: Optional[str] = None
    session_id: Optional[str] = None
    context: Optional[Dict[str, Any]] = None

class ChatResponse(BaseModel):
    response: str
    session_id: str
    domain: str
    confidence: float
    sources: List[Dict[str, Any]]
    suggested_actions: List[str] = []

class SessionInfo(BaseModel):
    session_id: str
    user_id: str
    domain: str
    created_at: datetime
    last_activity: datetime
    message_count: int
    context: Dict[str, Any]

class MessageHistory(BaseModel):
    messages: List[Dict[str, Any]]
    total_count: int
    session_info: SessionInfo

# Mock user for demonstration
class MockUser(BaseModel):
    id: str = "user123"
    username: str = "demo_user"
    allowed_domains: List[str] = ["general", "support", "sales", "engineering", "product"]
    preferences: Dict[str, Any] = {"default_domain": "general"}

def get_current_user() -> MockUser:
    """Mock user authentication - replace with real auth service"""
    return MockUser()

@app.get("/health")
async def health_check():
    """Health check endpoint"""
    return {
        "status": "healthy",
        "service": "chat-api",
        "version": "0.1.0",
        "active_sessions": session_manager.get_active_session_count(),
        "vector_service_status": await domain_client.health_check()
    }

@app.get("/domains")
async def get_available_domains(user: MockUser = Depends(get_current_user)):
    """Get domains available to the user"""
    try:
        domains = await domain_client.get_user_domains(user.allowed_domains)
        return {"domains": domains}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error fetching domains: {str(e)}")

@app.post("/chat", response_model=ChatResponse)
async def chat(
    request: ChatRequest,
    user: MockUser = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Process chat message and return response"""
    try:
        # Get or create session
        session_id = request.session_id or str(uuid.uuid4())
        session = session_manager.get_or_create_session(
            session_id=session_id,
            user_id=user.id,
            domain=request.domain or user.preferences.get("default_domain", "general"),
            db=db
        )

        # Check domain access
        if session.domain not in user.allowed_domains:
            raise HTTPException(status_code=403, detail=f"Access denied to domain: {session.domain}")

        # Process message
        response_data = await message_processor.process_message(
            message=request.message,
            session=session,
            user=user,
            context=request.context,
            db=db
        )

        # Update session activity
        session_manager.update_session_activity(session_id, db)

        return ChatResponse(**response_data)

    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error processing chat: {str(e)}")

@app.get("/sessions/{session_id}", response_model=MessageHistory)
async def get_session_history(
    session_id: str,
    limit: int = Query(50, description="Number of messages to retrieve"),
    offset: int = Query(0, description="Offset for pagination"),
    user: MockUser = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Get chat session history"""
    try:
        session = session_manager.get_session(session_id, db)
        if not session:
            raise HTTPException(status_code=404, detail="Session not found")

        # Check if user owns the session
        if session.user_id != user.id:
            raise HTTPException(status_code=403, detail="Access denied to this session")

        messages = session_manager.get_session_messages(session_id, db, limit, offset)
        
        return MessageHistory(
            messages=messages,
            total_count=session.message_count,
            session_info=SessionInfo(
                session_id=session.session_id,
                user_id=session.user_id,
                domain=session.domain,
                created_at=session.created_at,
                last_activity=session.last_activity,
                message_count=session.message_count,
                context=session.context or {}
            )
        )

    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error retrieving session: {str(e)}")

@app.get("/sessions")
async def list_user_sessions(
    user: MockUser = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """List all user sessions"""
    try:
        sessions = session_manager.get_user_sessions(user.id, db)
        return {
            "sessions": [
                {
                    "session_id": s.session_id,
                    "domain": s.domain,
                    "created_at": s.created_at,
                    "last_activity": s.last_activity,
                    "message_count": s.message_count
                }
                for s in sessions
            ]
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error listing sessions: {str(e)}")

@app.delete("/sessions/{session_id}")
async def delete_session(
    session_id: str,
    user: MockUser = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Delete a chat session"""
    try:
        session = session_manager.get_session(session_id, db)
        if not session:
            raise HTTPException(status_code=404, detail="Session not found")

        if session.user_id != user.id:
            raise HTTPException(status_code=403, detail="Access denied to this session")

        session_manager.delete_session(session_id, db)
        return {"message": "Session deleted successfully"}

    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error deleting session: {str(e)}")

# WebSocket endpoint for real-time chat
@app.websocket("/ws/{session_id}")
async def websocket_chat(
    websocket: WebSocket,
    session_id: str,
    domain: str = Query("general"),
    user_id: str = Query("user123")  # In real app, extract from JWT token
):
    """WebSocket endpoint for real-time chat"""
    await websocket.accept()
    
    # Create mock user for WebSocket (in real app, validate JWT token)
    user = MockUser(id=user_id)
    
    try:
        # Get database session
        db = next(get_db())
        
        # Get or create chat session
        session = session_manager.get_or_create_session(
            session_id=session_id,
            user_id=user.id,
            domain=domain,
            db=db
        )

        # Check domain access
        if domain not in user.allowed_domains:
            await websocket.send_json({
                "type": "error",
                "message": f"Access denied to domain: {domain}"
            })
            await websocket.close()
            return

        # Send welcome message
        await websocket.send_json({
            "type": "system",
            "message": f"Connected to {domain} domain",
            "session_id": session_id,
            "domain": domain
        })

        # Handle incoming messages
        while True:
            # Receive message from client
            data = await websocket.receive_json()
            message_text = data.get("message", "")
            
            if not message_text.strip():
                continue

            # Send typing indicator
            await websocket.send_json({
                "type": "typing",
                "message": "Assistant is typing..."
            })

            try:
                # Process message
                response_data = await message_processor.process_message(
                    message=message_text,
                    session=session,
                    user=user,
                    context=data.get("context"),
                    db=db
                )

                # Send response
                await websocket.send_json({
                    "type": "message",
                    "data": response_data
                })

                # Update session activity
                session_manager.update_session_activity(session_id, db)

            except Exception as e:
                await websocket.send_json({
                    "type": "error",
                    "message": f"Error processing message: {str(e)}"
                })

    except WebSocketDisconnect:
        print(f"WebSocket disconnected for session {session_id}")
    except Exception as e:
        print(f"WebSocket error: {str(e)}")
        await websocket.send_json({
            "type": "error",
            "message": "Connection error occurred"
        })
    finally:
        try:
            db.close()
        except:
            pass

@app.get("/demo", response_class=HTMLResponse)
async def get_demo_page():
    """Serve a simple demo chat interface"""
    html_content = """
    <!DOCTYPE html>
    <html>
    <head>
        <title>Multi-Domain RAG Chat Demo</title>
        <style>
            body { font-family: Arial, sans-serif; max-width: 800px; margin: 0 auto; padding: 20px; }
            .chat-container { border: 1px solid #ccc; height: 400px; overflow-y: auto; padding: 10px; margin: 10px 0; }
            .message { margin: 5px 0; padding: 5px; border-radius: 5px; }
            .user-message { background-color: #e3f2fd; text-align: right; }
            .assistant-message { background-color: #f1f8e9; }
            .system-message { background-color: #fff3e0; font-style: italic; }
            .error-message { background-color: #ffebee; color: #c62828; }
            input[type="text"] { width: 70%; padding: 10px; }
            button { padding: 10px 20px; margin: 5px; }
            select { padding: 5px; margin: 5px; }
        </style>
    </head>
    <body>
        <h1>Multi-Domain RAG Chat Demo</h1>
        
        <div>
            <label>Domain:</label>
            <select id="domain">
                <option value="general">General</option>
                <option value="support">Support</option>
                <option value="sales">Sales</option>
                <option value="engineering">Engineering</option>
                <option value="product">Product</option>
            </select>
            <button onclick="connect()">Connect</button>
            <button onclick="disconnect()">Disconnect</button>
        </div>
        
        <div id="chat" class="chat-container"></div>
        
        <div>
            <input type="text" id="messageInput" placeholder="Type your message..." onkeypress="handleKeyPress(event)">
            <button onclick="sendMessage()">Send</button>
        </div>

        <script>
            let ws = null;
            let sessionId = 'demo-' + Math.random().toString(36).substr(2, 9);

            function connect() {
                const domain = document.getElementById('domain').value;
                const wsUrl = `ws://localhost:8003/ws/${sessionId}?domain=${domain}&user_id=demo_user`;
                
                ws = new WebSocket(wsUrl);
                
                ws.onopen = function(event) {
                    addMessage('Connected to chat', 'system-message');
                };
                
                ws.onmessage = function(event) {
                    const data = JSON.parse(event.data);
                    
                    if (data.type === 'message') {
                        addMessage(`Assistant: ${data.data.response}`, 'assistant-message');
                        if (data.data.sources && data.data.sources.length > 0) {
                            addMessage(`Sources: ${data.data.sources.length} found`, 'system-message');
                        }
                    } else if (data.type === 'system') {
                        addMessage(data.message, 'system-message');
                    } else if (data.type === 'error') {
                        addMessage(`Error: ${data.message}`, 'error-message');
                    }
                };
                
                ws.onclose = function(event) {
                    addMessage('Disconnected from chat', 'system-message');
                };
                
                ws.onerror = function(error) {
                    addMessage('Connection error', 'error-message');
                };
            }

            function disconnect() {
                if (ws) {
                    ws.close();
                }
            }

            function sendMessage() {
                const input = document.getElementById('messageInput');
                const message = input.value.trim();
                
                if (message && ws && ws.readyState === WebSocket.OPEN) {
                    addMessage(`You: ${message}`, 'user-message');
                    ws.send(JSON.stringify({ message: message }));
                    input.value = '';
                }
            }

            function handleKeyPress(event) {
                if (event.key === 'Enter') {
                    sendMessage();
                }
            }

            function addMessage(text, className) {
                const chatDiv = document.getElementById('chat');
                const messageDiv = document.createElement('div');
                messageDiv.className = `message ${className}`;
                messageDiv.textContent = text;
                chatDiv.appendChild(messageDiv);
                chatDiv.scrollTop = chatDiv.scrollHeight;
            }
        </script>
    </body>
    </html>
    """
    return HTMLResponse(content=html_content)

if __name__ == "__main__":
    uvicorn.run(
        app,
        host="0.0.0.0",
        port=int(os.getenv("CHAT_API_PORT", 8003)),
        reload=False
    ) 
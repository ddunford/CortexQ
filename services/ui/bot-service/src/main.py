"""
Bot Integration Service
Provides Slack and Microsoft Teams integration for CortexQ system.
"""

from fastapi import FastAPI, HTTPException, Request, Depends
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from typing import Dict, List, Optional
import httpx
import logging
import os
from datetime import datetime

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

app = FastAPI(
    title="Bot Integration Service",
    description="Slack and Teams integration for CortexQ",
    version="1.0.0"
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Configuration
SLACK_BOT_TOKEN = os.getenv("SLACK_BOT_TOKEN")
SLACK_SIGNING_SECRET = os.getenv("SLACK_SIGNING_SECRET")
TEAMS_APP_ID = os.getenv("TEAMS_APP_ID")
TEAMS_APP_PASSWORD = os.getenv("TEAMS_APP_PASSWORD")
RAG_SERVICE_URL = os.getenv("RAG_SERVICE_URL", "http://localhost:8006")
CHAT_API_URL = os.getenv("CHAT_API_URL", "http://localhost:8003")

# Models
class SlackEvent(BaseModel):
    type: str
    event: Dict
    team_id: Optional[str] = None
    api_app_id: Optional[str] = None
    event_id: Optional[str] = None
    event_time: Optional[int] = None

class SlackMessage(BaseModel):
    channel: str
    user: str
    text: str
    ts: str
    team: Optional[str] = None

class TeamsMessage(BaseModel):
    id: str
    type: str
    text: str
    from_user: Dict
    conversation: Dict
    recipient: Dict

class BotResponse(BaseModel):
    text: str
    attachments: Optional[List[Dict]] = None
    blocks: Optional[List[Dict]] = None

# Bot Integration Manager
class BotIntegrationManager:
    def __init__(self):
        self.active_sessions = {}
        
    async def process_rag_query(self, query: str, user_id: str, domain: str = "general") -> str:
        """Process query through RAG service"""
        try:
            async with httpx.AsyncClient() as client:
                response = await client.post(
                    f"{RAG_SERVICE_URL}/process",
                    json={
                        "query": query,
                        "domain": domain,
                        "user_id": user_id,
                        "mode": "simple"
                    },
                    timeout=30.0
                )
                
                if response.status_code == 200:
                    data = response.json()
                    return data.get("response", "I couldn't process your request.")
                else:
                    logger.error(f"RAG service error: {response.status_code}")
                    return "Sorry, I'm having trouble processing your request right now."
                    
        except Exception as e:
            logger.error(f"Error calling RAG service: {e}")
            return "I encountered an error while processing your request."
    
    def format_slack_response(self, text: str, confidence: float = None) -> Dict:
        """Format response for Slack with rich formatting"""
        blocks = [
            {
                "type": "section",
                "text": {
                    "type": "mrkdwn",
                    "text": text
                }
            }
        ]
        
        if confidence:
            blocks.append({
                "type": "context",
                "elements": [
                    {
                        "type": "mrkdwn",
                        "text": f"Confidence: {confidence:.1%} | Powered by CortexQ"
                    }
                ]
            })
        
        return {"blocks": blocks}
    
    def format_teams_response(self, text: str, confidence: float = None) -> Dict:
        """Format response for Microsoft Teams"""
        response = {
            "type": "message",
            "text": text
        }
        
        if confidence:
            response["attachments"] = [{
                "contentType": "application/vnd.microsoft.card.adaptive",
                "content": {
                    "type": "AdaptiveCard",
                    "version": "1.0",
                    "body": [
                        {
                            "type": "TextBlock",
                            "text": text,
                            "wrap": True
                        },
                        {
                            "type": "TextBlock",
                            "text": f"Confidence: {confidence:.1%}",
                            "size": "small",
                            "color": "accent"
                        }
                    ]
                }
            }]
        
        return response

bot_manager = BotIntegrationManager()

# Health check
@app.get("/health")
async def health_check():
    return {
        "status": "healthy",
        "service": "bot-integration",
        "timestamp": datetime.utcnow().isoformat(),
        "integrations": {
            "slack": bool(SLACK_BOT_TOKEN),
            "teams": bool(TEAMS_APP_ID)
        }
    }

# Slack Integration Endpoints
@app.post("/slack/events")
async def slack_events(request: Request):
    """Handle Slack Events API"""
    try:
        body = await request.json()
        
        # Handle URL verification
        if body.get("type") == "url_verification":
            return {"challenge": body.get("challenge")}
        
        # Handle app mention events
        if body.get("type") == "event_callback":
            event = body.get("event", {})
            
            if event.get("type") == "app_mention":
                await handle_slack_mention(event)
            elif event.get("type") == "message" and event.get("channel_type") == "im":
                await handle_slack_direct_message(event)
        
        return {"status": "ok"}
        
    except Exception as e:
        logger.error(f"Error handling Slack event: {e}")
        raise HTTPException(status_code=500, detail="Internal server error")

@app.post("/slack/commands")
async def slack_slash_commands(request: Request):
    """Handle Slack slash commands"""
    try:
        form_data = await request.form()
        command = form_data.get("command")
        text = form_data.get("text", "")
        user_id = form_data.get("user_id")
        channel_id = form_data.get("channel_id")
        
        if command == "/rag":
            if not text.strip():
                return {
                    "response_type": "ephemeral",
                    "text": "Please provide a question. Usage: `/rag your question here`"
                }
            
            # Process query through RAG
            response = await bot_manager.process_rag_query(text, user_id)
            
            return {
                "response_type": "in_channel",
                **bot_manager.format_slack_response(response)
            }
        
        return {
            "response_type": "ephemeral",
            "text": "Unknown command"
        }
        
    except Exception as e:
        logger.error(f"Error handling Slack command: {e}")
        return {
            "response_type": "ephemeral",
            "text": "Sorry, I encountered an error processing your command."
        }

async def handle_slack_mention(event: Dict):
    """Handle Slack app mentions"""
    try:
        text = event.get("text", "")
        user = event.get("user")
        channel = event.get("channel")
        
        # Remove bot mention from text
        text = text.replace(f"<@{os.getenv('SLACK_BOT_USER_ID', '')}>", "").strip()
        
        if not text:
            text = "How can I help you?"
        
        # Process through RAG
        response = await bot_manager.process_rag_query(text, user)
        
        # Send response back to Slack
        await send_slack_message(channel, response)
        
    except Exception as e:
        logger.error(f"Error handling Slack mention: {e}")

async def handle_slack_direct_message(event: Dict):
    """Handle direct messages to the bot"""
    try:
        text = event.get("text", "")
        user = event.get("user")
        channel = event.get("channel")
        
        # Process through RAG
        response = await bot_manager.process_rag_query(text, user)
        
        # Send response back to Slack
        await send_slack_message(channel, response)
        
    except Exception as e:
        logger.error(f"Error handling Slack DM: {e}")

async def send_slack_message(channel: str, text: str):
    """Send message to Slack channel"""
    try:
        if not SLACK_BOT_TOKEN:
            logger.warning("Slack bot token not configured")
            return
        
        async with httpx.AsyncClient() as client:
            response = await client.post(
                "https://slack.com/api/chat.postMessage",
                headers={"Authorization": f"Bearer {SLACK_BOT_TOKEN}"},
                json={
                    "channel": channel,
                    **bot_manager.format_slack_response(text)
                }
            )
            
            if response.status_code != 200:
                logger.error(f"Failed to send Slack message: {response.text}")
                
    except Exception as e:
        logger.error(f"Error sending Slack message: {e}")

# Microsoft Teams Integration
@app.post("/teams/messages")
async def teams_messages(message: TeamsMessage):
    """Handle Microsoft Teams messages"""
    try:
        text = message.text
        user_id = message.from_user.get("id")
        
        # Process through RAG
        response = await bot_manager.process_rag_query(text, user_id)
        
        # Format for Teams
        teams_response = bot_manager.format_teams_response(response)
        
        return teams_response
        
    except Exception as e:
        logger.error(f"Error handling Teams message: {e}")
        raise HTTPException(status_code=500, detail="Internal server error")

# Webhook endpoints for external integrations
@app.post("/webhooks/slack")
async def slack_webhook(request: Request):
    """Generic Slack webhook handler"""
    try:
        body = await request.json()
        logger.info(f"Received Slack webhook: {body}")
        
        # Process webhook data
        return {"status": "received"}
        
    except Exception as e:
        logger.error(f"Error handling Slack webhook: {e}")
        raise HTTPException(status_code=500, detail="Internal server error")

@app.post("/webhooks/teams")
async def teams_webhook(request: Request):
    """Generic Teams webhook handler"""
    try:
        body = await request.json()
        logger.info(f"Received Teams webhook: {body}")
        
        # Process webhook data
        return {"status": "received"}
        
    except Exception as e:
        logger.error(f"Error handling Teams webhook: {e}")
        raise HTTPException(status_code=500, detail="Internal server error")

# Configuration endpoints
@app.get("/config")
async def get_bot_config():
    """Get bot configuration status"""
    return {
        "slack": {
            "configured": bool(SLACK_BOT_TOKEN),
            "bot_token": bool(SLACK_BOT_TOKEN),
            "signing_secret": bool(SLACK_SIGNING_SECRET)
        },
        "teams": {
            "configured": bool(TEAMS_APP_ID),
            "app_id": bool(TEAMS_APP_ID),
            "app_password": bool(TEAMS_APP_PASSWORD)
        },
        "services": {
            "rag_service": RAG_SERVICE_URL,
            "chat_api": CHAT_API_URL
        }
    }

@app.get("/integrations/status")
async def integration_status():
    """Get status of all bot integrations"""
    return {
        "active_sessions": len(bot_manager.active_sessions),
        "integrations": {
            "slack": {
                "enabled": bool(SLACK_BOT_TOKEN),
                "status": "active" if SLACK_BOT_TOKEN else "not_configured"
            },
            "teams": {
                "enabled": bool(TEAMS_APP_ID),
                "status": "active" if TEAMS_APP_ID else "not_configured"
            }
        },
        "last_updated": datetime.utcnow().isoformat()
    }

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8012) 
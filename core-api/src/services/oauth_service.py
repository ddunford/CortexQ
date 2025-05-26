"""
OAuth Service for Data Source Connectors
Handles OAuth2 authentication flows with external services
"""

import os
import secrets
import hashlib
import base64
from datetime import datetime, timedelta
from typing import Dict, Any, Optional, Tuple
from urllib.parse import urlencode, parse_qs, urlparse
import aiohttp
import json

from schemas.connector_schemas import ConnectorType


class OAuthConfig:
    """OAuth configuration for different connector types"""
    
    CONFIGS = {
        ConnectorType.JIRA: {
            "auth_url": "https://auth.atlassian.com/authorize",
            "token_url": "https://auth.atlassian.com/oauth/token",
            "scopes": ["read:jira-work", "read:jira-user"],
            "response_type": "code",
            "grant_type": "authorization_code"
        },
        ConnectorType.GITHUB: {
            "auth_url": "https://github.com/login/oauth/authorize",
            "token_url": "https://github.com/login/oauth/access_token",
            "scopes": ["repo", "read:user", "read:org"],
            "response_type": "code",
            "grant_type": "authorization_code"
        },
        ConnectorType.CONFLUENCE: {
            "auth_url": "https://auth.atlassian.com/authorize",
            "token_url": "https://auth.atlassian.com/oauth/token",
            "scopes": ["read:confluence-content.all", "read:confluence-space.summary"],
            "response_type": "code",
            "grant_type": "authorization_code"
        },
        ConnectorType.GOOGLE_DRIVE: {
            "auth_url": "https://accounts.google.com/o/oauth2/v2/auth",
            "token_url": "https://oauth2.googleapis.com/token",
            "scopes": ["https://www.googleapis.com/auth/drive.readonly"],
            "response_type": "code",
            "grant_type": "authorization_code"
        },
        ConnectorType.SLACK: {
            "auth_url": "https://slack.com/oauth/v2/authorize",
            "token_url": "https://slack.com/api/oauth.v2.access",
            "scopes": ["channels:read", "channels:history", "files:read"],
            "response_type": "code",
            "grant_type": "authorization_code"
        }
    }


class OAuthService:
    """Service for handling OAuth2 authentication flows"""
    
    def __init__(self, redis_client=None):
        """Initialize OAuth service with optional Redis for state storage"""
        self.redis_client = redis_client
        self.base_redirect_uri = os.getenv("OAUTH_REDIRECT_URI", "http://localhost:3000/auth/callback")
        
        # Get client credentials from environment
        self.client_credentials = {
            ConnectorType.JIRA: {
                "client_id": os.getenv("JIRA_CLIENT_ID"),
                "client_secret": os.getenv("JIRA_CLIENT_SECRET")
            },
            ConnectorType.GITHUB: {
                "client_id": os.getenv("GITHUB_CLIENT_ID"),
                "client_secret": os.getenv("GITHUB_CLIENT_SECRET")
            },
            ConnectorType.CONFLUENCE: {
                "client_id": os.getenv("CONFLUENCE_CLIENT_ID"),
                "client_secret": os.getenv("CONFLUENCE_CLIENT_SECRET")
            },
            ConnectorType.GOOGLE_DRIVE: {
                "client_id": os.getenv("GOOGLE_DRIVE_CLIENT_ID"),
                "client_secret": os.getenv("GOOGLE_DRIVE_CLIENT_SECRET")
            },
            ConnectorType.SLACK: {
                "client_id": os.getenv("SLACK_CLIENT_ID"),
                "client_secret": os.getenv("SLACK_CLIENT_SECRET")
            }
        }
    
    async def initiate_oauth_flow(
        self, 
        connector_type: ConnectorType,
        organization_id: str,
        domain: str,
        user_id: str,
        redirect_uri: Optional[str] = None
    ) -> Tuple[str, str]:
        """
        Initiate OAuth flow for a connector type
        
        Returns:
            Tuple of (auth_url: str, state: str)
        """
        if connector_type not in OAuthConfig.CONFIGS:
            raise ValueError(f"OAuth not supported for connector type: {connector_type}")
        
        config = OAuthConfig.CONFIGS[connector_type]
        credentials = self.client_credentials.get(connector_type)
        
        if not credentials or not credentials.get("client_id"):
            raise ValueError(f"OAuth credentials not configured for {connector_type}")
        
        # Generate state parameter for security
        state = self._generate_state(organization_id, domain, user_id, connector_type)
        
        # Store state in Redis if available
        if self.redis_client:
            state_data = {
                "organization_id": organization_id,
                "domain": domain,
                "user_id": user_id,
                "connector_type": connector_type,
                "created_at": datetime.utcnow().isoformat()
            }
            await self._store_state(state, state_data)
        
        # Build authorization URL
        auth_params = {
            "client_id": credentials["client_id"],
            "response_type": config["response_type"],
            "scope": " ".join(config["scopes"]),
            "state": state,
            "redirect_uri": redirect_uri or self.base_redirect_uri
        }
        
        # Add PKCE for enhanced security (if supported)
        if connector_type in [ConnectorType.GITHUB, ConnectorType.GOOGLE_DRIVE]:
            code_verifier = self._generate_code_verifier()
            code_challenge = self._generate_code_challenge(code_verifier)
            auth_params.update({
                "code_challenge": code_challenge,
                "code_challenge_method": "S256"
            })
            
            # Store code verifier for token exchange
            if self.redis_client:
                await self._store_code_verifier(state, code_verifier)
        
        auth_url = f"{config['auth_url']}?{urlencode(auth_params)}"
        
        return auth_url, state
    
    async def handle_oauth_callback(
        self, 
        code: str, 
        state: str,
        redirect_uri: Optional[str] = None
    ) -> Tuple[bool, Dict[str, Any]]:
        """
        Handle OAuth callback and exchange code for tokens
        
        Returns:
            Tuple of (success: bool, result: Dict)
        """
        try:
            # Validate and retrieve state data
            state_data = await self._get_state_data(state)
            if not state_data:
                return False, {"error": "Invalid or expired state parameter"}
            
            connector_type = ConnectorType(state_data["connector_type"])
            config = OAuthConfig.CONFIGS[connector_type]
            credentials = self.client_credentials[connector_type]
            
            # Prepare token exchange request
            token_params = {
                "client_id": credentials["client_id"],
                "client_secret": credentials["client_secret"],
                "code": code,
                "grant_type": config["grant_type"],
                "redirect_uri": redirect_uri or self.base_redirect_uri
            }
            
            # Add PKCE code verifier if used
            if connector_type in [ConnectorType.GITHUB, ConnectorType.GOOGLE_DRIVE]:
                code_verifier = await self._get_code_verifier(state)
                if code_verifier:
                    token_params["code_verifier"] = code_verifier
            
            # Exchange code for tokens
            tokens = await self._exchange_code_for_tokens(config["token_url"], token_params)
            
            if not tokens:
                return False, {"error": "Failed to exchange code for tokens"}
            
            # Clean up stored state
            await self._cleanup_state(state)
            
            # Return success with tokens and state data
            return True, {
                "tokens": tokens,
                "state_data": state_data,
                "connector_type": connector_type
            }
            
        except Exception as e:
            return False, {"error": str(e)}
    
    async def refresh_access_token(
        self, 
        connector_type: ConnectorType,
        refresh_token: str
    ) -> Optional[Dict[str, Any]]:
        """
        Refresh access token using refresh token
        
        Returns:
            New token data or None if refresh failed
        """
        if connector_type not in OAuthConfig.CONFIGS:
            return None
        
        config = OAuthConfig.CONFIGS[connector_type]
        credentials = self.client_credentials.get(connector_type)
        
        if not credentials:
            return None
        
        token_params = {
            "client_id": credentials["client_id"],
            "client_secret": credentials["client_secret"],
            "refresh_token": refresh_token,
            "grant_type": "refresh_token"
        }
        
        return await self._exchange_code_for_tokens(config["token_url"], token_params)
    
    def _generate_state(self, organization_id: str, domain: str, user_id: str, connector_type: ConnectorType) -> str:
        """Generate secure state parameter"""
        random_bytes = secrets.token_bytes(32)
        state_data = f"{organization_id}:{domain}:{user_id}:{connector_type}:{datetime.utcnow().isoformat()}"
        state_hash = hashlib.sha256(state_data.encode() + random_bytes).hexdigest()
        return base64.urlsafe_b64encode(state_hash.encode()).decode().rstrip('=')
    
    def _generate_code_verifier(self) -> str:
        """Generate PKCE code verifier"""
        return base64.urlsafe_b64encode(secrets.token_bytes(32)).decode().rstrip('=')
    
    def _generate_code_challenge(self, code_verifier: str) -> str:
        """Generate PKCE code challenge"""
        digest = hashlib.sha256(code_verifier.encode()).digest()
        return base64.urlsafe_b64encode(digest).decode().rstrip('=')
    
    async def _store_state(self, state: str, state_data: Dict[str, Any]):
        """Store state data in Redis"""
        if self.redis_client:
            key = f"oauth_state:{state}"
            await self.redis_client.setex(key, 600, json.dumps(state_data))  # 10 minute expiry
    
    async def _get_state_data(self, state: str) -> Optional[Dict[str, Any]]:
        """Retrieve state data from Redis"""
        if not self.redis_client:
            return None
        
        key = f"oauth_state:{state}"
        data = await self.redis_client.get(key)
        
        if data:
            return json.loads(data)
        return None
    
    async def _store_code_verifier(self, state: str, code_verifier: str):
        """Store PKCE code verifier"""
        if self.redis_client:
            key = f"oauth_verifier:{state}"
            await self.redis_client.setex(key, 600, code_verifier)  # 10 minute expiry
    
    async def _get_code_verifier(self, state: str) -> Optional[str]:
        """Retrieve PKCE code verifier"""
        if not self.redis_client:
            return None
        
        key = f"oauth_verifier:{state}"
        return await self.redis_client.get(key)
    
    async def _cleanup_state(self, state: str):
        """Clean up stored state and verifier"""
        if self.redis_client:
            keys = [f"oauth_state:{state}", f"oauth_verifier:{state}"]
            for key in keys:
                await self.redis_client.delete(key)
    
    async def _exchange_code_for_tokens(self, token_url: str, params: Dict[str, str]) -> Optional[Dict[str, Any]]:
        """Exchange authorization code for access tokens"""
        try:
            async with aiohttp.ClientSession() as session:
                headers = {
                    "Accept": "application/json",
                    "Content-Type": "application/x-www-form-urlencoded"
                }
                
                async with session.post(token_url, data=params, headers=headers) as response:
                    if response.status == 200:
                        token_data = await response.json()
                        
                        # Standardize token response format
                        standardized = {
                            "access_token": token_data.get("access_token"),
                            "refresh_token": token_data.get("refresh_token"),
                            "token_type": token_data.get("token_type", "Bearer"),
                            "expires_in": token_data.get("expires_in"),
                            "scope": token_data.get("scope"),
                            "created_at": datetime.utcnow().isoformat()
                        }
                        
                        # Calculate expiry time if expires_in is provided
                        if token_data.get("expires_in"):
                            expires_at = datetime.utcnow() + timedelta(seconds=int(token_data["expires_in"]))
                            standardized["expires_at"] = expires_at.isoformat()
                        
                        return standardized
                    else:
                        error_text = await response.text()
                        print(f"Token exchange failed: {response.status} - {error_text}")
                        return None
                        
        except Exception as e:
            print(f"Error exchanging code for tokens: {e}")
            return None
    
    def is_token_expired(self, token_data: Dict[str, Any]) -> bool:
        """Check if access token is expired"""
        expires_at = token_data.get("expires_at")
        if not expires_at:
            return False
        
        try:
            expiry_time = datetime.fromisoformat(expires_at.replace('Z', '+00:00'))
            return datetime.utcnow() > expiry_time
        except (ValueError, TypeError):
            return False
    
    async def ensure_valid_token(self, connector_type: ConnectorType, auth_config: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        """Ensure we have a valid access token, refreshing if necessary"""
        if not self.is_token_expired(auth_config):
            return auth_config
        
        refresh_token = auth_config.get("refresh_token")
        if not refresh_token:
            return None
        
        # Attempt to refresh the token
        new_tokens = await self.refresh_access_token(connector_type, refresh_token)
        if new_tokens:
            # Merge new tokens with existing config
            updated_config = auth_config.copy()
            updated_config.update(new_tokens)
            return updated_config
        
        return None 
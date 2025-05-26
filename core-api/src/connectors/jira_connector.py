"""
Jira Connector Implementation
Handles data synchronization with Atlassian Jira
"""

import aiohttp
from datetime import datetime
from typing import Dict, List, Any, Optional, Tuple
from urllib.parse import urljoin

from services.base_connector import BaseConnector, Document, SyncResult, SyncResultStatus
from schemas.connector_schemas import ConnectorType


class JiraConnector(BaseConnector):
    """Connector for Atlassian Jira integration"""
    
    def __init__(self, config):
        super().__init__(config)
        self.base_url = self.auth_config.get("instance_url", "").rstrip('/')
        self.api_version = "3"  # Jira Cloud API v3
        
    async def authenticate(self) -> Tuple[bool, Optional[str]]:
        """Authenticate with Jira using OAuth2 or API token"""
        try:
            # Test authentication by fetching user info
            headers = await self._get_auth_headers()
            if not headers:
                return False, "No authentication credentials available"
            
            async with aiohttp.ClientSession() as session:
                url = f"{self.base_url}/rest/api/{self.api_version}/myself"
                
                async with session.get(url, headers=headers) as response:
                    if response.status == 200:
                        user_info = await response.json()
                        return True, None
                    elif response.status == 401:
                        return False, "Invalid credentials"
                    else:
                        error_text = await response.text()
                        return False, f"Authentication failed: {response.status} - {error_text}"
                        
        except Exception as e:
            return False, f"Authentication error: {str(e)}"
    
    async def test_connection(self) -> Tuple[bool, Dict[str, Any]]:
        """Test connection to Jira and return instance information"""
        try:
            auth_success, auth_error = await self.authenticate()
            if not auth_success:
                return False, {"error": auth_error}
            
            headers = await self._get_auth_headers()
            
            async with aiohttp.ClientSession() as session:
                # Get server info
                server_url = f"{self.base_url}/rest/api/{self.api_version}/serverInfo"
                
                async with session.get(server_url, headers=headers) as response:
                    if response.status == 200:
                        server_info = await response.json()
                        
                        # Get accessible projects
                        projects_url = f"{self.base_url}/rest/api/{self.api_version}/project"
                        async with session.get(projects_url, headers=headers) as proj_response:
                            projects = []
                            if proj_response.status == 200:
                                projects_data = await proj_response.json()
                                projects = [{"key": p["key"], "name": p["name"]} for p in projects_data[:5]]
                        
                        return True, {
                            "server_info": {
                                "version": server_info.get("version"),
                                "deployment_type": server_info.get("deploymentType"),
                                "base_url": server_info.get("baseUrl")
                            },
                            "accessible_projects": projects,
                            "connection_test_time": datetime.utcnow().isoformat()
                        }
                    else:
                        error_text = await response.text()
                        return False, {"error": f"Failed to get server info: {response.status} - {error_text}"}
                        
        except Exception as e:
            return False, {"error": f"Connection test failed: {str(e)}"}
    
    async def fetch_data(self, since: Optional[datetime] = None) -> List[Dict[str, Any]]:
        """Fetch issues from Jira"""
        try:
            headers = await self._get_auth_headers()
            if not headers:
                raise Exception("No authentication headers available")
            
            all_issues = []
            start_at = 0
            max_results = self._get_batch_size()
            
            # Build JQL query
            jql_parts = []
            
            # Add project filter if specified
            project_filter = self._get_sync_filters().get("projects")
            if project_filter:
                if isinstance(project_filter, list):
                    projects_str = ",".join(project_filter)
                    jql_parts.append(f"project in ({projects_str})")
                else:
                    jql_parts.append(f"project = {project_filter}")
            
            # Add date filter for incremental sync
            if since:
                since_str = since.strftime("%Y-%m-%d %H:%M")
                jql_parts.append(f"updated >= '{since_str}'")
            
            # Add status filter if specified
            status_filter = self._get_sync_filters().get("statuses")
            if status_filter:
                if isinstance(status_filter, list):
                    statuses_str = ",".join([f'"{s}"' for s in status_filter])
                    jql_parts.append(f"status in ({statuses_str})")
            
            jql = " AND ".join(jql_parts) if jql_parts else "order by updated DESC"
            
            async with aiohttp.ClientSession() as session:
                while True:
                    # Search for issues
                    search_url = f"{self.base_url}/rest/api/{self.api_version}/search"
                    params = {
                        "jql": jql,
                        "startAt": start_at,
                        "maxResults": max_results,
                        "expand": "changelog,comments,attachments",
                        "fields": "summary,description,status,assignee,reporter,created,updated,priority,issuetype,project,components,labels,fixVersions"
                    }
                    
                    async with session.get(search_url, headers=headers, params=params) as response:
                        if response.status != 200:
                            error_text = await response.text()
                            raise Exception(f"Failed to fetch issues: {response.status} - {error_text}")
                        
                        data = await response.json()
                        issues = data.get("issues", [])
                        
                        # Filter issues based on sync configuration
                        filtered_issues = [issue for issue in issues if self._should_include_issue(issue)]
                        all_issues.extend(filtered_issues)
                        
                        # Check if we have more results
                        total = data.get("total", 0)
                        if start_at + max_results >= total:
                            break
                        
                        start_at += max_results
                        
                        # Respect rate limits
                        await self._rate_limit_delay()
            
            return all_issues
            
        except Exception as e:
            raise Exception(f"Error fetching Jira data: {str(e)}")
    
    async def transform_data(self, raw_data: List[Dict[str, Any]]) -> List[Document]:
        """Transform Jira issues to Document format"""
        documents = []
        
        for issue in raw_data:
            try:
                fields = issue.get("fields", {})
                
                # Extract basic information
                issue_key = issue.get("key", "")
                summary = fields.get("summary", "")
                description = fields.get("description", "")
                
                # Build content text
                content_parts = []
                
                if summary:
                    content_parts.append(f"Summary: {summary}")
                
                if description:
                    # Handle Atlassian Document Format (ADF) if present
                    if isinstance(description, dict):
                        description_text = self._extract_text_from_adf(description)
                    else:
                        description_text = str(description)
                    content_parts.append(f"Description: {description_text}")
                
                # Add comments
                comments = self._extract_comments(issue)
                if comments:
                    content_parts.append(f"Comments:\n{comments}")
                
                content = "\n\n".join(content_parts)
                
                # Extract metadata
                metadata = {
                    "source_type": "jira",
                    "issue_key": issue_key,
                    "issue_id": issue.get("id"),
                    "status": fields.get("status", {}).get("name"),
                    "priority": fields.get("priority", {}).get("name"),
                    "issue_type": fields.get("issuetype", {}).get("name"),
                    "project": {
                        "key": fields.get("project", {}).get("key"),
                        "name": fields.get("project", {}).get("name")
                    },
                    "assignee": self._extract_user_info(fields.get("assignee")),
                    "reporter": self._extract_user_info(fields.get("reporter")),
                    "created": fields.get("created"),
                    "updated": fields.get("updated"),
                    "labels": fields.get("labels", []),
                    "components": [comp.get("name") for comp in fields.get("components", [])],
                    "fix_versions": [ver.get("name") for ver in fields.get("fixVersions", [])]
                }
                
                # Apply field mapping if configured
                if self.mapping_config:
                    metadata = self._apply_field_mapping(metadata)
                
                # Create document
                document = Document(
                    title=f"[{issue_key}] {summary}",
                    content=content,
                    source_id=issue_key,
                    source_type="jira_issue",
                    metadata=metadata,
                    organization_id=self.config.organization_id,
                    domain=self.config.domain,
                    created_at=self._parse_jira_date(fields.get("created")),
                    updated_at=self._parse_jira_date(fields.get("updated"))
                )
                
                documents.append(document)
                
            except Exception as e:
                print(f"Error transforming Jira issue {issue.get('key', 'unknown')}: {e}")
                continue
        
        return documents
    
    async def _get_auth_headers(self) -> Optional[Dict[str, str]]:
        """Get authentication headers for API requests"""
        auth_type = self.auth_config.get("type")
        
        if auth_type == "oauth":
            access_token = self.auth_config.get("access_token")
            if access_token:
                return {
                    "Authorization": f"Bearer {access_token}",
                    "Accept": "application/json",
                    "Content-Type": "application/json"
                }
        
        elif auth_type == "api_key":
            api_key = self.auth_config.get("api_key")
            username = self.auth_config.get("username")
            if api_key and username:
                import base64
                credentials = base64.b64encode(f"{username}:{api_key}".encode()).decode()
                return {
                    "Authorization": f"Basic {credentials}",
                    "Accept": "application/json",
                    "Content-Type": "application/json"
                }
        
        return None
    
    def _should_include_issue(self, issue: Dict[str, Any]) -> bool:
        """Check if an issue should be included based on filters"""
        # Use base class filtering
        if not self._should_include_record(issue):
            return False
        
        # Additional Jira-specific filtering
        fields = issue.get("fields", {})
        
        # Filter by issue type
        issue_type_filter = self._get_sync_filters().get("issue_types")
        if issue_type_filter:
            issue_type = fields.get("issuetype", {}).get("name")
            if isinstance(issue_type_filter, list):
                if issue_type not in issue_type_filter:
                    return False
            elif issue_type != issue_type_filter:
                return False
        
        return True
    
    def _extract_text_from_adf(self, adf_content: Dict[str, Any]) -> str:
        """Extract plain text from Atlassian Document Format"""
        def extract_text_recursive(node):
            if isinstance(node, dict):
                text_parts = []
                
                # Handle text nodes
                if node.get("type") == "text":
                    return node.get("text", "")
                
                # Handle other node types
                if "content" in node:
                    for child in node["content"]:
                        text_parts.append(extract_text_recursive(child))
                
                return " ".join(text_parts)
            
            elif isinstance(node, list):
                return " ".join([extract_text_recursive(item) for item in node])
            
            else:
                return str(node) if node else ""
        
        return extract_text_recursive(adf_content)
    
    def _extract_comments(self, issue: Dict[str, Any]) -> str:
        """Extract comments from issue"""
        comments = []
        
        # Get comments from fields
        fields = issue.get("fields", {})
        comment_data = fields.get("comment", {})
        
        if isinstance(comment_data, dict) and "comments" in comment_data:
            for comment in comment_data["comments"]:
                author = self._extract_user_info(comment.get("author"))
                body = comment.get("body", "")
                
                # Handle ADF format in comments
                if isinstance(body, dict):
                    body = self._extract_text_from_adf(body)
                
                created = comment.get("created", "")
                
                comment_text = f"[{created}] {author.get('displayName', 'Unknown')}: {body}"
                comments.append(comment_text)
        
        return "\n".join(comments)
    
    def _extract_user_info(self, user_data: Optional[Dict[str, Any]]) -> Dict[str, Any]:
        """Extract user information from Jira user object"""
        if not user_data:
            return {}
        
        return {
            "accountId": user_data.get("accountId"),
            "displayName": user_data.get("displayName"),
            "emailAddress": user_data.get("emailAddress"),
            "active": user_data.get("active", True)
        }
    
    def _parse_jira_date(self, date_str: Optional[str]) -> Optional[datetime]:
        """Parse Jira date string to datetime object"""
        if not date_str:
            return None
        
        try:
            # Jira uses ISO 8601 format
            return datetime.fromisoformat(date_str.replace('Z', '+00:00'))
        except (ValueError, TypeError):
            return None
    
    async def _rate_limit_delay(self):
        """Add delay to respect Jira rate limits"""
        import asyncio
        # Jira Cloud allows 10 requests per second per app
        await asyncio.sleep(0.1)  # 100ms delay 
"""
API Connector Implementations
"""

import asyncio
import base64
from abc import ABC, abstractmethod
from typing import Dict, Any, AsyncGenerator, List
import httpx
import logging
from datetime import datetime, timedelta

logger = logging.getLogger(__name__)


class BaseConnector(ABC):
    """Base class for all API connectors"""
    
    def __init__(self, config: Dict[str, Any]):
        self.config = config
        self.client = httpx.AsyncClient(timeout=30.0)
    
    @abstractmethod
    async def test_connection(self) -> Dict[str, Any]:
        """Test the connection to the external API"""
        pass
    
    @abstractmethod
    async def sync_data(self) -> AsyncGenerator[Dict[str, Any], None]:
        """Sync data from the external API"""
        pass
    
    async def close(self):
        """Close the HTTP client"""
        await self.client.aclose()


class JiraConnector(BaseConnector):
    """Jira API connector"""
    
    async def test_connection(self) -> Dict[str, Any]:
        """Test Jira connection"""
        
        server_url = self.config.get("server_url")
        username = self.config.get("username")
        api_token = self.config.get("api_token")
        
        if not all([server_url, username, api_token]):
            raise ValueError("Missing required Jira configuration")
        
        # Create auth header
        auth_string = f"{username}:{api_token}"
        auth_bytes = auth_string.encode('ascii')
        auth_header = base64.b64encode(auth_bytes).decode('ascii')
        
        headers = {
            "Authorization": f"Basic {auth_header}",
            "Accept": "application/json"
        }
        
        try:
            response = await self.client.get(
                f"{server_url}/rest/api/3/myself",
                headers=headers
            )
            response.raise_for_status()
            
            user_info = response.json()
            return {
                "status": "success",
                "user": user_info.get("displayName"),
                "account_id": user_info.get("accountId")
            }
            
        except Exception as e:
            raise Exception(f"Jira connection test failed: {str(e)}")
    
    async def sync_data(self) -> AsyncGenerator[Dict[str, Any], None]:
        """Sync issues from Jira"""
        
        server_url = self.config.get("server_url")
        username = self.config.get("username")
        api_token = self.config.get("api_token")
        project_keys = self.config.get("project_keys", [])
        issue_types = self.config.get("issue_types", [])
        max_results = self.config.get("max_results", 100)
        
        # Create auth header
        auth_string = f"{username}:{api_token}"
        auth_bytes = auth_string.encode('ascii')
        auth_header = base64.b64encode(auth_bytes).decode('ascii')
        
        headers = {
            "Authorization": f"Basic {auth_header}",
            "Accept": "application/json"
        }
        
        # Build JQL query
        jql_parts = []
        if project_keys:
            projects = ",".join(project_keys)
            jql_parts.append(f"project in ({projects})")
        if issue_types:
            types = ",".join([f'"{t}"' for t in issue_types])
            jql_parts.append(f"issuetype in ({types})")
        
        # Add date filter for recent updates (last 30 days)
        jql_parts.append("updated >= -30d")
        
        jql = " AND ".join(jql_parts) if jql_parts else "updated >= -30d"
        
        start_at = 0
        while True:
            try:
                params = {
                    "jql": jql,
                    "startAt": start_at,
                    "maxResults": min(max_results, 100),
                    "fields": "summary,description,status,priority,assignee,reporter,created,updated,issuetype,project"
                }
                
                response = await self.client.get(
                    f"{server_url}/rest/api/3/search",
                    headers=headers,
                    params=params
                )
                response.raise_for_status()
                
                data = response.json()
                issues = data.get("issues", [])
                
                if not issues:
                    break
                
                for issue in issues:
                    yield {
                        "id": issue["key"],
                        "title": issue["fields"]["summary"],
                        "description": issue["fields"].get("description", {}).get("content", [{}])[0].get("content", [{}])[0].get("text", "") if issue["fields"].get("description") else "",
                        "status": issue["fields"]["status"]["name"],
                        "priority": issue["fields"]["priority"]["name"] if issue["fields"].get("priority") else "None",
                        "assignee": issue["fields"]["assignee"]["displayName"] if issue["fields"].get("assignee") else "Unassigned",
                        "reporter": issue["fields"]["reporter"]["displayName"] if issue["fields"].get("reporter") else "Unknown",
                        "created": issue["fields"]["created"],
                        "updated": issue["fields"]["updated"],
                        "issue_type": issue["fields"]["issuetype"]["name"],
                        "project": issue["fields"]["project"]["name"],
                        "url": f"{server_url}/browse/{issue['key']}",
                        "source": "jira",
                        "content_type": "issue"
                    }
                
                # Check if there are more results
                if len(issues) < params["maxResults"]:
                    break
                
                start_at += len(issues)
                
            except Exception as e:
                logger.error(f"Error syncing Jira data: {e}")
                break


class GitHubConnector(BaseConnector):
    """GitHub API connector"""
    
    async def test_connection(self) -> Dict[str, Any]:
        """Test GitHub connection"""
        
        api_token = self.config.get("api_token")
        if not api_token:
            raise ValueError("Missing GitHub API token")
        
        headers = {
            "Authorization": f"token {api_token}",
            "Accept": "application/vnd.github.v3+json"
        }
        
        try:
            response = await self.client.get(
                "https://api.github.com/user",
                headers=headers
            )
            response.raise_for_status()
            
            user_info = response.json()
            return {
                "status": "success",
                "user": user_info.get("login"),
                "name": user_info.get("name")
            }
            
        except Exception as e:
            raise Exception(f"GitHub connection test failed: {str(e)}")
    
    async def sync_data(self) -> AsyncGenerator[Dict[str, Any], None]:
        """Sync issues and PRs from GitHub"""
        
        api_token = self.config.get("api_token")
        repositories = self.config.get("repositories", [])
        include_issues = self.config.get("include_issues", True)
        include_pull_requests = self.config.get("include_pull_requests", True)
        max_results = self.config.get("max_results", 100)
        
        headers = {
            "Authorization": f"token {api_token}",
            "Accept": "application/vnd.github.v3+json"
        }
        
        for repo in repositories:
            if "/" not in repo:
                logger.warning(f"Invalid repository format: {repo}")
                continue
            
            owner, repo_name = repo.split("/", 1)
            
            # Sync issues
            if include_issues:
                async for item in self._sync_github_items(
                    f"https://api.github.com/repos/{owner}/{repo_name}/issues",
                    headers, max_results, "issue", repo
                ):
                    yield item
            
            # Sync pull requests
            if include_pull_requests:
                async for item in self._sync_github_items(
                    f"https://api.github.com/repos/{owner}/{repo_name}/pulls",
                    headers, max_results, "pull_request", repo
                ):
                    yield item
    
    async def _sync_github_items(self, url: str, headers: Dict[str, str], max_results: int, item_type: str, repo: str) -> AsyncGenerator[Dict[str, Any], None]:
        """Helper method to sync GitHub items (issues or PRs)"""
        
        page = 1
        per_page = min(max_results, 100)
        total_fetched = 0
        
        while total_fetched < max_results:
            try:
                params = {
                    "page": page,
                    "per_page": per_page,
                    "state": "all",
                    "sort": "updated",
                    "direction": "desc"
                }
                
                response = await self.client.get(url, headers=headers, params=params)
                response.raise_for_status()
                
                items = response.json()
                if not items:
                    break
                
                for item in items:
                    if total_fetched >= max_results:
                        break
                    
                    # Skip pull requests when fetching issues (GitHub includes PRs in issues endpoint)
                    if item_type == "issue" and "pull_request" in item:
                        continue
                    
                    yield {
                        "id": f"{repo}#{item['number']}",
                        "title": item["title"],
                        "description": item.get("body", ""),
                        "status": item["state"],
                        "author": item["user"]["login"],
                        "created": item["created_at"],
                        "updated": item["updated_at"],
                        "url": item["html_url"],
                        "repository": repo,
                        "labels": [label["name"] for label in item.get("labels", [])],
                        "source": "github",
                        "content_type": item_type
                    }
                    
                    total_fetched += 1
                
                if len(items) < per_page:
                    break
                
                page += 1
                
            except Exception as e:
                logger.error(f"Error syncing GitHub {item_type}s: {e}")
                break


class ConfluenceConnector(BaseConnector):
    """Confluence API connector"""
    
    async def test_connection(self) -> Dict[str, Any]:
        """Test Confluence connection"""
        
        server_url = self.config.get("server_url")
        username = self.config.get("username")
        api_token = self.config.get("api_token")
        
        if not all([server_url, username, api_token]):
            raise ValueError("Missing required Confluence configuration")
        
        # Create auth header
        auth_string = f"{username}:{api_token}"
        auth_bytes = auth_string.encode('ascii')
        auth_header = base64.b64encode(auth_bytes).decode('ascii')
        
        headers = {
            "Authorization": f"Basic {auth_header}",
            "Accept": "application/json"
        }
        
        try:
            response = await self.client.get(
                f"{server_url}/rest/api/user/current",
                headers=headers
            )
            response.raise_for_status()
            
            user_info = response.json()
            return {
                "status": "success",
                "user": user_info.get("displayName"),
                "username": user_info.get("username")
            }
            
        except Exception as e:
            raise Exception(f"Confluence connection test failed: {str(e)}")
    
    async def sync_data(self) -> AsyncGenerator[Dict[str, Any], None]:
        """Sync pages from Confluence"""
        
        server_url = self.config.get("server_url")
        username = self.config.get("username")
        api_token = self.config.get("api_token")
        space_keys = self.config.get("space_keys", [])
        content_types = self.config.get("content_types", ["page"])
        max_results = self.config.get("max_results", 100)
        
        # Create auth header
        auth_string = f"{username}:{api_token}"
        auth_bytes = auth_string.encode('ascii')
        auth_header = base64.b64encode(auth_bytes).decode('ascii')
        
        headers = {
            "Authorization": f"Basic {auth_header}",
            "Accept": "application/json"
        }
        
        for content_type in content_types:
            start = 0
            limit = min(max_results, 50)
            
            while True:
                try:
                    params = {
                        "start": start,
                        "limit": limit,
                        "expand": "body.storage,space,version,ancestors"
                    }
                    
                    # Add space filter if specified
                    if space_keys:
                        params["spaceKey"] = ",".join(space_keys)
                    
                    response = await self.client.get(
                        f"{server_url}/rest/api/content",
                        headers=headers,
                        params=params
                    )
                    response.raise_for_status()
                    
                    data = response.json()
                    results = data.get("results", [])
                    
                    if not results:
                        break
                    
                    for page in results:
                        # Extract text content from storage format
                        body_content = ""
                        if page.get("body", {}).get("storage", {}).get("value"):
                            body_content = page["body"]["storage"]["value"]
                        
                        yield {
                            "id": page["id"],
                            "title": page["title"],
                            "content": body_content,
                            "space": page["space"]["name"],
                            "space_key": page["space"]["key"],
                            "created": page["version"]["when"],
                            "updated": page["version"]["when"],
                            "version": page["version"]["number"],
                            "url": f"{server_url}/pages/viewpage.action?pageId={page['id']}",
                            "source": "confluence",
                            "content_type": page["type"]
                        }
                    
                    # Check if there are more results
                    if len(results) < limit:
                        break
                    
                    start += len(results)
                    
                except Exception as e:
                    logger.error(f"Error syncing Confluence data: {e}")
                    break 
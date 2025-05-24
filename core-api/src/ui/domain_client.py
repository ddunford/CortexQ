"""
Domain Vector Client
Handles communication with the multi-domain vector service.
"""

import asyncio
from typing import List, Dict, Any, Optional
import httpx
from datetime import datetime


class DomainVectorClient:
    """Client for interacting with the multi-domain vector service"""
    
    def __init__(self, base_url: str):
        self.base_url = base_url.rstrip('/')
        self.client = httpx.AsyncClient(timeout=30.0)
    
    async def health_check(self) -> Dict[str, Any]:
        """Check health of vector service"""
        try:
            response = await self.client.get(f"{self.base_url}/health")
            if response.status_code == 200:
                return response.json()
            else:
                return {"status": "unhealthy", "error": f"HTTP {response.status_code}"}
        except Exception as e:
            return {"status": "unhealthy", "error": str(e)}
    
    async def get_user_domains(self, allowed_domains: List[str]) -> List[Dict[str, Any]]:
        """Get domain configurations for user's allowed domains"""
        try:
            response = await self.client.get(f"{self.base_url}/domains")
            if response.status_code == 200:
                data = response.json()
                # Filter to user's allowed domains
                user_domains = [
                    domain for domain in data.get("domains", [])
                    if domain["name"] in allowed_domains
                ]
                return user_domains
            else:
                return []
        except Exception as e:
            print(f"Error fetching domains: {e}")
            return []
    
    async def search_domain(self, domain: str, query: str, top_k: int = 10) -> Dict[str, Any]:
        """Search within a specific domain"""
        try:
            payload = {
                "query": query,
                "top_k": top_k
            }
            
            response = await self.client.post(
                f"{self.base_url}/search/{domain}",
                json=payload
            )
            
            if response.status_code == 200:
                return response.json()
            elif response.status_code == 403:
                return {
                    "results": [],
                    "total_found": 0,
                    "error": "Access denied to domain",
                    "searched_domains": []
                }
            else:
                return {
                    "results": [],
                    "total_found": 0,
                    "error": f"Search failed: HTTP {response.status_code}",
                    "searched_domains": []
                }
                
        except Exception as e:
            return {
                "results": [],
                "total_found": 0,
                "error": f"Search error: {str(e)}",
                "searched_domains": []
            }
    
    async def search_cross_domain(self, domains: List[str], query: str, top_k: int = 10) -> Dict[str, Any]:
        """Search across multiple domains"""
        try:
            payload = {
                "query": query,
                "domains": domains,
                "top_k": top_k
            }
            
            response = await self.client.post(
                f"{self.base_url}/search/cross-domain",
                json=payload
            )
            
            if response.status_code == 200:
                return response.json()
            else:
                return {
                    "results": [],
                    "total_found": 0,
                    "error": f"Cross-domain search failed: HTTP {response.status_code}",
                    "searched_domains": []
                }
                
        except Exception as e:
            return {
                "results": [],
                "total_found": 0,
                "error": f"Cross-domain search error: {str(e)}",
                "searched_domains": []
            }
    
    async def auto_search(self, query: str, domains: Optional[List[str]] = None, top_k: int = 10) -> Dict[str, Any]:
        """Auto-search with optional domain filtering"""
        try:
            params = {
                "q": query,
                "top_k": top_k
            }
            
            if domains:
                params["domains"] = ",".join(domains)
            
            response = await self.client.get(
                f"{self.base_url}/search",
                params=params
            )
            
            if response.status_code == 200:
                return response.json()
            else:
                return {
                    "results": [],
                    "total_found": 0,
                    "error": f"Auto-search failed: HTTP {response.status_code}",
                    "searched_domains": []
                }
                
        except Exception as e:
            return {
                "results": [],
                "total_found": 0,
                "error": f"Auto-search error: {str(e)}",
                "searched_domains": []
            }
    
    async def get_domain_stats(self, domain: Optional[str] = None) -> Dict[str, Any]:
        """Get statistics for domains"""
        try:
            params = {}
            if domain:
                params["domain"] = domain
            
            response = await self.client.get(
                f"{self.base_url}/stats",
                params=params
            )
            
            if response.status_code == 200:
                return response.json()
            else:
                return {"error": f"Stats request failed: HTTP {response.status_code}"}
                
        except Exception as e:
            return {"error": f"Stats error: {str(e)}"}
    
    async def classify_domain(self, query: str) -> str:
        """Simple domain classification based on query content"""
        # Basic keyword-based classification
        # In a real system, this would be more sophisticated
        
        query_lower = query.lower()
        
        # Support domain keywords
        support_keywords = ["error", "bug", "crash", "issue", "problem", "help", "troubleshoot", "broken", "not working"]
        if any(keyword in query_lower for keyword in support_keywords):
            return "support"
        
        # Sales domain keywords
        sales_keywords = ["price", "cost", "feature", "capabilities", "compliance", "security", "competitor", "demo"]
        if any(keyword in query_lower for keyword in sales_keywords):
            return "sales"
        
        # Engineering domain keywords
        engineering_keywords = ["api", "code", "deploy", "architecture", "technical", "documentation", "integrate"]
        if any(keyword in query_lower for keyword in engineering_keywords):
            return "engineering"
        
        # Product domain keywords
        product_keywords = ["roadmap", "feature request", "user", "feedback", "requirement", "planning"]
        if any(keyword in query_lower for keyword in product_keywords):
            return "product"
        
        # Default to general
        return "general"
    
    async def close(self):
        """Close the HTTP client"""
        await self.client.aclose() 
"""
Training & Documentation Workflow Engine
Implements specialized workflow for training and help requests
"""

import logging
from typing import Dict, Any, List, Optional

import httpx
from sqlalchemy.orm import Session

from models import TrainingResult
from config import settings

logger = logging.getLogger(__name__)


class TrainingWorkflow:
    """Training and documentation workflow"""
    
    def __init__(self):
        self.vector_client = httpx.AsyncClient(timeout=30.0)
    
    async def execute(
        self, 
        query: str, 
        context: Optional[Dict[str, Any]] = None,
        db: Session = None
    ) -> TrainingResult:
        """Execute training workflow"""
        
        logger.info(f"Executing training workflow for query: {query[:100]}...")
        
        try:
            # Step 1: Search documentation and training materials
            docs_results = await self._search_documentation(query)
            
            # Step 2: Generate step-by-step guide
            step_by_step = self._generate_step_by_step(query, docs_results)
            
            # Step 3: Extract code examples
            code_examples = self._extract_code_examples(docs_results)
            
            # Step 4: Find additional resources
            resources = self._find_resources(query, docs_results)
            
            # Step 5: Find related documentation
            related_docs = self._find_related_docs(docs_results)
            
            # Step 6: Determine difficulty level
            difficulty = self._determine_difficulty(query)
            
            return TrainingResult(
                topic=self._extract_topic(query),
                step_by_step=step_by_step,
                code_examples=code_examples,
                resources=resources,
                related_docs=related_docs,
                difficulty_level=difficulty
            )
            
        except Exception as e:
            logger.error(f"Error in training workflow: {e}")
            return TrainingResult(
                topic="Training request",
                step_by_step=["Please refer to our documentation or contact support"],
                code_examples=[],
                resources=[{"type": "support", "url": "mailto:support@example.com", "title": "Contact Support"}],
                related_docs=[],
                difficulty_level="unknown"
            )
    
    async def _search_documentation(self, query: str) -> List[Dict[str, Any]]:
        """Search documentation across relevant domains"""
        all_results = []
        
        # Search multiple domains for comprehensive coverage
        domains = ["general", "engineering", "product"]
        
        for domain in domains:
            try:
                search_url = f"{settings.VECTOR_SERVICE_URL}/search/{domain}"
                search_payload = {
                    "query": query,
                    "top_k": 5
                }
                
                response = await self.vector_client.post(search_url, json=search_payload)
                
                if response.status_code == 200:
                    results = response.json()
                    domain_results = results.get("results", [])
                    
                    # Add domain info to results
                    for result in domain_results:
                        result["source_domain"] = domain
                    
                    all_results.extend(domain_results)
                
            except Exception as e:
                logger.warning(f"Failed to search {domain} domain: {e}")
        
        # Sort by relevance and return top results
        all_results.sort(key=lambda x: x.get("similarity", 0.0), reverse=True)
        return all_results[:10]
    
    def _extract_topic(self, query: str) -> str:
        """Extract the main topic from the query"""
        
        # Common training topics
        topics = {
            "deploy": "Deployment",
            "install": "Installation", 
            "configure": "Configuration",
            "setup": "Setup",
            "api": "API Usage",
            "integrate": "Integration",
            "troubleshoot": "Troubleshooting",
            "security": "Security",
            "performance": "Performance",
            "monitor": "Monitoring"
        }
        
        query_lower = query.lower()
        
        for keyword, topic in topics.items():
            if keyword in query_lower:
                return topic
        
        # Extract main subject from query
        words = [word for word in query.split() if len(word) > 3]
        return " ".join(words[:3]).title() if words else "General Help"
    
    def _generate_step_by_step(self, query: str, docs_results: List[Dict[str, Any]]) -> List[str]:
        """Generate step-by-step instructions"""
        
        steps = []
        
        # Extract procedural content from search results
        for result in docs_results[:3]:
            content = result.get("content", "")
            
            # Look for numbered steps or bullet points
            lines = content.split("\n")
            for line in lines:
                line = line.strip()
                if (line.startswith(("1.", "2.", "3.", "•", "-", "*")) or 
                    "step" in line.lower()):
                    steps.append(line)
        
        # If no specific steps found, generate generic ones based on query
        if not steps:
            steps = self._generate_generic_steps(query)
        
        return steps[:8]  # Limit to 8 steps
    
    def _generate_generic_steps(self, query: str) -> List[str]:
        """Generate generic steps based on query type"""
        
        query_lower = query.lower()
        
        if "install" in query_lower:
            return [
                "1. Check system requirements",
                "2. Download the installation package",
                "3. Run the installer with appropriate permissions",
                "4. Follow the setup wizard",
                "5. Verify the installation"
            ]
        elif "configure" in query_lower or "setup" in query_lower:
            return [
                "1. Open the configuration file or settings panel",
                "2. Review default settings",
                "3. Modify settings according to your requirements",
                "4. Save the configuration",
                "5. Restart the service if required",
                "6. Test the configuration"
            ]
        elif "deploy" in query_lower:
            return [
                "1. Prepare the deployment environment",
                "2. Build the application",
                "3. Configure deployment settings",
                "4. Deploy to target environment",
                "5. Verify deployment status",
                "6. Test functionality"
            ]
        elif "api" in query_lower:
            return [
                "1. Obtain API credentials",
                "2. Review API documentation",
                "3. Set up authentication",
                "4. Make a test API call",
                "5. Handle responses and errors"
            ]
        else:
            return [
                "1. Review the documentation",
                "2. Understand the requirements",
                "3. Follow the recommended process",
                "4. Test your implementation",
                "5. Troubleshoot if needed"
            ]
    
    def _extract_code_examples(self, docs_results: List[Dict[str, Any]]) -> List[Dict[str, str]]:
        """Extract code examples from documentation"""
        
        code_examples = []
        
        for result in docs_results:
            content = result.get("content", "")
            
            # Look for code blocks (simplified detection)
            if "```" in content or "    " in content:  # Code blocks or indented code
                
                # Extract language and code (simplified)
                lines = content.split("\n")
                current_code = []
                in_code_block = False
                language = "text"
                
                for line in lines:
                    if line.strip().startswith("```"):
                        if not in_code_block:
                            in_code_block = True
                            language = line.replace("```", "").strip() or "text"
                        else:
                            if current_code:
                                code_examples.append({
                                    "language": language,
                                    "code": "\n".join(current_code),
                                    "description": f"Example from {result.get('source_domain', 'documentation')}"
                                })
                            current_code = []
                            in_code_block = False
                    elif in_code_block:
                        current_code.append(line)
                    elif line.startswith("    ") and not in_code_block:
                        # Indented code (likely Python or similar)
                        code_examples.append({
                            "language": "python",
                            "code": line.strip(),
                            "description": "Code snippet"
                        })
        
        return code_examples[:5]  # Limit to 5 examples
    
    def _find_resources(self, query: str, docs_results: List[Dict[str, Any]]) -> List[Dict[str, str]]:
        """Find additional learning resources"""
        
        resources = []
        
        # Add documentation links from search results
        for result in docs_results[:3]:
            metadata = result.get("metadata", {})
            if metadata.get("url"):
                resources.append({
                    "type": "documentation",
                    "title": metadata.get("title", "Documentation"),
                    "url": metadata["url"],
                    "description": result.get("content", "")[:100] + "..."
                })
        
        # Add generic resources based on query type
        query_lower = query.lower()
        
        if "api" in query_lower:
            resources.append({
                "type": "api_docs",
                "title": "API Reference",
                "url": "https://docs.example.com/api",
                "description": "Complete API documentation with examples"
            })
        
        if "deploy" in query_lower:
            resources.append({
                "type": "guide",
                "title": "Deployment Guide",
                "url": "https://docs.example.com/deployment",
                "description": "Step-by-step deployment instructions"
            })
        
        if "troubleshoot" in query_lower:
            resources.append({
                "type": "troubleshooting",
                "title": "Troubleshooting Guide",
                "url": "https://docs.example.com/troubleshooting",
                "description": "Common issues and solutions"
            })
        
        # Add generic helpful resources
        resources.extend([
            {
                "type": "tutorial",
                "title": "Video Tutorials",
                "url": "https://tutorials.example.com",
                "description": "Step-by-step video guides"
            },
            {
                "type": "community",
                "title": "Community Forum",
                "url": "https://forum.example.com",
                "description": "Ask questions and get help from the community"
            }
        ])
        
        return resources[:8]  # Limit to 8 resources
    
    def _find_related_docs(self, docs_results: List[Dict[str, Any]]) -> List[Dict[str, str]]:
        """Find related documentation"""
        
        related = []
        
        for result in docs_results:
            metadata = result.get("metadata", {})
            
            related.append({
                "title": metadata.get("title", "Related Documentation"),
                "url": metadata.get("url", "#"),
                "summary": result.get("content", "")[:200] + "...",
                "relevance": str(round(result.get("similarity", 0.0), 2))
            })
        
        return related[:5]  # Limit to 5 related docs
    
    def _determine_difficulty(self, query: str) -> str:
        """Determine the difficulty level of the topic"""
        
        query_lower = query.lower()
        
        beginner_indicators = ["how to", "getting started", "intro", "basic", "simple", "first time"]
        advanced_indicators = ["advanced", "complex", "optimize", "performance", "custom", "enterprise"]
        
        if any(indicator in query_lower for indicator in advanced_indicators):
            return "advanced"
        elif any(indicator in query_lower for indicator in beginner_indicators):
            return "beginner"
        else:
            return "intermediate"
    
    async def close(self):
        """Close HTTP clients"""
        await self.vector_client.aclose() 
"""
Feature Request Workflow Engine
Implements specialized workflow for feature request processing
"""

import logging
from typing import Dict, Any, List, Optional

import httpx
from sqlalchemy.orm import Session

from models.workflow_models import FeatureAnalysisResult, Priority
from models import FeatureRequest
from config import settings

logger = logging.getLogger(__name__)


class FeatureRequestWorkflow:
    """Feature request analysis and processing workflow"""
    
    def __init__(self):
        self.vector_client = httpx.AsyncClient(timeout=30.0)
    
    async def execute(
        self, 
        query: str, 
        context: Optional[Dict[str, Any]] = None,
        db: Session = None
    ) -> FeatureAnalysisResult:
        """Execute feature request workflow"""
        
        logger.info(f"Executing feature request workflow for query: {query[:100]}...")
        
        try:
            # Step 1: Search existing feature requests
            existing_requests = self._search_existing_requests(query, db)
            
            # Step 2: Search for existing features in documentation
            existing_features = await self._search_existing_features(query)
            
            # Step 3: Analyze business impact
            business_impact = self._analyze_business_impact(query, context)
            
            # Step 4: Generate implementation notes
            implementation_notes = self._generate_implementation_notes(query, existing_features)
            
            # Step 5: Determine next steps
            next_steps = self._determine_next_steps(existing_requests, existing_features)
            
            # Step 6: Estimate effort
            estimated_effort = self._estimate_effort(query)
            
            return FeatureAnalysisResult(
                request_summary=self._generate_summary(query),
                status=self._determine_status(existing_requests, existing_features),
                existing_features=existing_features,
                implementation_notes=implementation_notes,
                business_impact=business_impact,
                next_steps=next_steps,
                estimated_effort=estimated_effort,
                similar_requests=existing_requests
            )
            
        except Exception as e:
            logger.error(f"Error in feature request workflow: {e}")
            return FeatureAnalysisResult(
                request_summary="Feature request analysis failed",
                status="analysis_error",
                existing_features=[],
                implementation_notes=f"Analysis error: {str(e)}",
                business_impact="Unable to determine impact",
                next_steps=["Manual review required"],
                estimated_effort="Unknown",
                similar_requests=[]
            )
    
    def _search_existing_requests(self, query: str, db: Session) -> List[Dict[str, Any]]:
        """Search for similar existing feature requests"""
        if not db:
            return []
        
        try:
            requests = db.query(FeatureRequest).all()
            similar = []
            
            query_words = set(query.lower().split())
            
            for req in requests:
                title_words = set(req.title.lower().split())
                desc_words = set(req.description.lower().split())
                
                title_overlap = len(query_words.intersection(title_words))
                desc_overlap = len(query_words.intersection(desc_words))
                
                similarity = (title_overlap * 2 + desc_overlap) / len(query_words)
                
                if similarity > 0.3:  # 30% similarity threshold
                    similar.append({
                        "id": str(req.id),
                        "title": req.title,
                        "status": req.status,
                        "priority": req.priority,
                        "votes": req.user_votes,
                        "similarity": similarity
                    })
            
            similar.sort(key=lambda x: x["similarity"], reverse=True)
            return similar[:5]
            
        except Exception as e:
            logger.error(f"Error searching existing requests: {e}")
            return []
    
    async def _search_existing_features(self, query: str) -> List[Dict[str, Any]]:
        """Search for existing features in product documentation"""
        try:
            # Search product domain for existing features
            search_url = f"{settings.VECTOR_SERVICE_URL}/search/product"
            search_payload = {
                "query": f"feature {query}",
                "top_k": 5
            }
            
            response = await self.vector_client.post(search_url, json=search_payload)
            
            if response.status_code == 200:
                results = response.json()
                features = []
                
                for result in results.get("results", []):
                    features.append({
                        "title": result.get("metadata", {}).get("title", "Feature"),
                        "description": result.get("content", "")[:300],
                        "relevance": result.get("similarity", 0.0),
                        "domain": result.get("domain", "product")
                    })
                
                return features
            else:
                logger.warning(f"Feature search failed: {response.status_code}")
                return []
                
        except Exception as e:
            logger.error(f"Error searching existing features: {e}")
            return []
    
    def _analyze_business_impact(self, query: str, context: Optional[Dict[str, Any]]) -> str:
        """Analyze potential business impact of the feature"""
        
        impact_keywords = {
            "high": ["revenue", "customer", "competitive", "critical", "essential"],
            "medium": ["improve", "efficiency", "user experience", "productivity"],
            "low": ["nice to have", "convenience", "minor", "optional"]
        }
        
        query_lower = query.lower()
        
        for level, keywords in impact_keywords.items():
            if any(keyword in query_lower for keyword in keywords):
                if level == "high":
                    return "High business impact - directly affects revenue or customer satisfaction"
                elif level == "medium":
                    return "Medium business impact - improves operational efficiency"
                else:
                    return "Low business impact - quality of life improvement"
        
        return "Business impact requires further analysis"
    
    def _generate_implementation_notes(self, query: str, existing_features: List[Dict[str, Any]]) -> str:
        """Generate technical implementation notes"""
        
        notes = []
        
        # Check for existing similar features
        if existing_features:
            notes.append("Consider extending existing features:")
            for feature in existing_features[:2]:
                notes.append(f"- {feature['title']}")
        
        # Add general implementation considerations
        query_lower = query.lower()
        
        if "api" in query_lower:
            notes.append("API implementation considerations: versioning, rate limiting, documentation")
        
        if "ui" in query_lower or "interface" in query_lower:
            notes.append("UI/UX considerations: responsive design, accessibility, user testing")
        
        if "data" in query_lower or "database" in query_lower:
            notes.append("Data considerations: schema changes, migration strategy, performance impact")
        
        if "integration" in query_lower:
            notes.append("Integration considerations: third-party APIs, authentication, error handling")
        
        return "\n".join(notes) if notes else "Standard feature implementation process"
    
    def _determine_next_steps(
        self, 
        existing_requests: List[Dict[str, Any]], 
        existing_features: List[Dict[str, Any]]
    ) -> List[str]:
        """Determine next steps for the feature request"""
        
        steps = []
        
        if existing_features:
            steps.append("Review existing similar features for enhancement opportunities")
        
        if existing_requests:
            similar_active = [r for r in existing_requests if r["status"] in ["submitted", "reviewing"]]
            if similar_active:
                steps.append("Consider consolidating with similar pending requests")
            else:
                steps.append("Reference completed similar requests for insights")
        
        steps.extend([
            "Create detailed technical specification",
            "Estimate development effort and timeline",
            "Schedule product team review",
            "Gather user feedback and validate requirements"
        ])
        
        return steps
    
    def _estimate_effort(self, query: str) -> str:
        """Estimate development effort based on request complexity"""
        
        query_lower = query.lower()
        
        complex_indicators = ["integration", "api", "database", "algorithm", "machine learning"]
        medium_indicators = ["ui", "feature", "enhancement", "improve"]
        simple_indicators = ["button", "text", "color", "minor", "small"]
        
        if any(indicator in query_lower for indicator in complex_indicators):
            return "Large (4-8 weeks)"
        elif any(indicator in query_lower for indicator in medium_indicators):
            return "Medium (2-4 weeks)"
        elif any(indicator in query_lower for indicator in simple_indicators):
            return "Small (1-2 weeks)"
        else:
            return "Medium (2-4 weeks) - requires detailed analysis"
    
    def _generate_summary(self, query: str) -> str:
        """Generate a concise summary of the feature request"""
        
        # Extract key action words
        action_words = ["add", "create", "implement", "build", "develop", "enable", "support"]
        
        words = query.lower().split()
        key_words = [word for word in words if len(word) > 3][:8]
        
        return f"Feature request: {' '.join(key_words)}"
    
    def _determine_status(
        self, 
        existing_requests: List[Dict[str, Any]], 
        existing_features: List[Dict[str, Any]]
    ) -> str:
        """Determine the status of this feature request"""
        
        if existing_features:
            return "existing_feature_available"
        
        active_similar = [r for r in existing_requests if r["status"] in ["submitted", "reviewing", "planned"]]
        if active_similar:
            return "similar_request_pending"
        
        completed_similar = [r for r in existing_requests if r["status"] == "completed"]
        if completed_similar:
            return "similar_request_completed"
        
        return "new_request"
    
    async def close(self):
        """Close HTTP clients"""
        await self.vector_client.aclose() 
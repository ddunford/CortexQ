"""
RAG Processor - Core Retrieval-Augmented Generation Logic
Handles search orchestration, response generation, and quality assessment
"""

import asyncio
import hashlib
import time
import logging
from typing import Dict, Any, List, Optional, Tuple
from datetime import datetime

import httpx
import redis
from sqlalchemy.orm import Session

from models import (
    RAGRequest, RAGResponse, RAGMode, ResponseType, SourceInfo, 
    SearchResult, SearchResponse, RAGExecution, SourceQuality
)
from config import settings

logger = logging.getLogger(__name__)


class RAGProcessor:
    """Core RAG processing engine"""
    
    def __init__(self):
        self.vector_client = httpx.AsyncClient(timeout=30.0)
        self.agent_client = httpx.AsyncClient(timeout=30.0)
        self.classification_client = httpx.AsyncClient(timeout=30.0)
        
        # Initialize Redis cache
        try:
            self.redis_client = redis.from_url(settings.REDIS_URL)
            self.cache_enabled = True
        except Exception as e:
            logger.warning(f"Redis not available, caching disabled: {e}")
            self.redis_client = None
            self.cache_enabled = False
    
    async def process_query(
        self, 
        request: RAGRequest, 
        db: Session
    ) -> RAGResponse:
        """Main entry point for RAG processing"""
        
        start_time = time.time()
        
        # Create execution record
        execution = RAGExecution(
            query=request.query,
            domain=request.domain,
            user_id=request.user_id,
            session_id=request.session_id,
            mode=request.mode,
            max_results=request.max_results,
            confidence_threshold=request.confidence_threshold
        )
        
        db.add(execution)
        db.commit()
        db.refresh(execution)
        
        try:
            # Check cache first
            cache_key = self._generate_cache_key(request)
            cached_response = await self._get_cached_response(cache_key)
            
            if cached_response and not request.force_refresh_cache:
                execution.cache_hit = True
                execution.cache_key = cache_key
                execution.completed_at = datetime.utcnow()
                db.commit()
                
                cached_response["execution_id"] = str(execution.id)
                cached_response["cache_hit"] = True
                return RAGResponse(**cached_response)
            
            # Perform search based on mode
            search_start = time.time()
            search_response = await self._perform_search(request)
            search_time = int((time.time() - search_start) * 1000)
            
            # Generate response
            generation_start = time.time()
            response_data = await self._generate_response(
                request, search_response, execution.id
            )
            generation_time = int((time.time() - generation_start) * 1000)
            
            # Update execution record
            total_time = int((time.time() - start_time) * 1000)
            execution.search_results = search_response.dict()
            execution.response_type = response_data["response_type"]
            execution.generated_response = response_data["response"]
            execution.confidence_score = response_data["confidence"]
            execution.source_count = len(response_data["sources"])
            execution.search_time_ms = search_time
            execution.generation_time_ms = generation_time
            execution.total_time_ms = total_time
            execution.cache_key = cache_key
            execution.completed_at = datetime.utcnow()
            
            db.commit()
            
            # Cache the response
            if self.cache_enabled and settings.CACHE_RAG_RESPONSES:
                await self._cache_response(cache_key, response_data)
            
            # Update source quality metrics
            await self._update_source_quality(search_response.results, db)
            
            # Prepare final response
            rag_response = RAGResponse(
                execution_id=str(execution.id),
                processing_time_ms=total_time,
                **response_data
            )
            
            return rag_response
            
        except Exception as e:
            logger.error(f"Error in RAG processing: {e}")
            
            # Update execution with error
            execution.error_message = str(e)
            execution.completed_at = datetime.utcnow()
            db.commit()
            
            # Return error response
            return RAGResponse(
                execution_id=str(execution.id),
                response=f"I apologize, but I encountered an error processing your request: {str(e)}",
                response_type=ResponseType.NO_RESULTS,
                confidence=0.0,
                sources=[],
                source_count=0,
                domain_searched=request.domain,
                mode_used=request.mode,
                processing_time_ms=int((time.time() - start_time) * 1000),
                suggested_actions=["Please try rephrasing your question", "Contact support for assistance"]
            )
    
    async def _perform_search(self, request: RAGRequest) -> SearchResponse:
        """Perform search based on the specified mode"""
        
        if request.mode == RAGMode.SIMPLE:
            return await self._simple_domain_search(request)
        elif request.mode == RAGMode.CROSS_DOMAIN:
            return await self._cross_domain_search(request)
        elif request.mode == RAGMode.AGENT_ENHANCED:
            return await self._agent_enhanced_search(request)
        elif request.mode == RAGMode.HYBRID:
            return await self._hybrid_search(request)
        else:
            # Default to simple search
            return await self._simple_domain_search(request)
    
    async def _simple_domain_search(self, request: RAGRequest) -> SearchResponse:
        """Perform simple domain-specific search"""
        
        try:
            search_url = f"{settings.VECTOR_SERVICE_URL}/search/{request.domain}"
            search_payload = {
                "query": request.query,
                "top_k": request.max_results
            }
            
            response = await self.vector_client.post(search_url, json=search_payload)
            
            if response.status_code == 200:
                data = response.json()
                results = []
                
                for result in data.get("results", []):
                    if result.get("similarity", 0.0) >= request.confidence_threshold:
                        results.append(SearchResult(
                            content=result.get("content", ""),
                            metadata=result.get("metadata", {}),
                            similarity=result.get("similarity", 0.0),
                            domain=request.domain,
                            source_id=result.get("metadata", {}).get("file_id", "unknown")
                        ))
                
                return SearchResponse(
                    results=results,
                    total_found=len(results),
                    search_time_ms=data.get("search_time_ms", 0),
                    domains_searched=[request.domain]
                )
            else:
                return SearchResponse(
                    results=[],
                    total_found=0,
                    search_time_ms=0,
                    domains_searched=[request.domain],
                    error=f"Vector search failed with status {response.status_code}"
                )
                
        except Exception as e:
            logger.error(f"Error in simple domain search: {e}")
            return SearchResponse(
                results=[],
                total_found=0,
                search_time_ms=0,
                domains_searched=[request.domain],
                error=str(e)
            )
    
    async def _cross_domain_search(self, request: RAGRequest) -> SearchResponse:
        """Perform cross-domain search across allowed domains"""
        
        try:
            search_url = f"{settings.VECTOR_SERVICE_URL}/search/auto"
            search_payload = {
                "query": request.query,
                "domains": request.allowed_domains,
                "top_k": request.max_results
            }
            
            response = await self.vector_client.post(search_url, json=search_payload)
            
            if response.status_code == 200:
                data = response.json()
                results = []
                
                for result in data.get("results", []):
                    if result.get("similarity", 0.0) >= request.confidence_threshold:
                        results.append(SearchResult(
                            content=result.get("content", ""),
                            metadata=result.get("metadata", {}),
                            similarity=result.get("similarity", 0.0),
                            domain=result.get("domain", "unknown"),
                            source_id=result.get("metadata", {}).get("file_id", "unknown")
                        ))
                
                return SearchResponse(
                    results=results,
                    total_found=len(results),
                    search_time_ms=data.get("search_time_ms", 0),
                    domains_searched=data.get("domains_searched", request.allowed_domains)
                )
            else:
                return SearchResponse(
                    results=[],
                    total_found=0,
                    search_time_ms=0,
                    domains_searched=request.allowed_domains,
                    error=f"Cross-domain search failed with status {response.status_code}"
                )
                
        except Exception as e:
            logger.error(f"Error in cross-domain search: {e}")
            return SearchResponse(
                results=[],
                total_found=0,
                search_time_ms=0,
                domains_searched=request.allowed_domains,
                error=str(e)
            )
    
    async def _agent_enhanced_search(self, request: RAGRequest) -> SearchResponse:
        """Perform search enhanced with agent workflow integration"""
        
        # First classify the query to determine intent
        try:
            classification_url = f"{settings.CLASSIFICATION_SERVICE_URL}/classify"
            classification_payload = {
                "text": request.query,
                "domain": request.domain
            }
            
            classification_response = await self.classification_client.post(
                classification_url, json=classification_payload
            )
            
            if classification_response.status_code == 200:
                classification_data = classification_response.json()
                intent = classification_data.get("intent", "general")
                confidence = classification_data.get("confidence", 0.5)
                
                # If high confidence in specific intent, use agent workflow
                if confidence > 0.7 and intent in ["bug_report", "feature_request", "training"]:
                    agent_url = f"{settings.AGENT_SERVICE_URL}/execute"
                    agent_payload = {
                        "query": request.query,
                        "intent": intent,
                        "confidence": confidence,
                        "classification_metadata": classification_data.get("metadata"),
                        "user_context": request.context,
                        "user_id": request.user_id,
                        "session_id": request.session_id,
                        "domain": request.domain
                    }
                    
                    agent_response = await self.agent_client.post(agent_url, json=agent_payload)
                    
                    if agent_response.status_code == 200:
                        agent_data = agent_response.json()
                        
                        # Convert agent response to search results format
                        results = [SearchResult(
                            content=agent_data.get("response", ""),
                            metadata={
                                "agent_workflow": True,
                                "workflow_type": intent,
                                "workflow_id": agent_data.get("workflow_id"),
                                "title": f"{intent.replace('_', ' ').title()} Response"
                            },
                            similarity=agent_data.get("confidence", 0.8),
                            domain=request.domain,
                            source_id=f"agent_{agent_data.get('workflow_id', 'unknown')}"
                        )]
                        
                        return SearchResponse(
                            results=results,
                            total_found=1,
                            search_time_ms=agent_data.get("processing_time_ms", 0),
                            domains_searched=[request.domain]
                        )
            
            # Fall back to regular cross-domain search if agent workflow didn't work
            return await self._cross_domain_search(request)
            
        except Exception as e:
            logger.error(f"Error in agent-enhanced search: {e}")
            # Fall back to regular search
            return await self._cross_domain_search(request)
    
    async def _hybrid_search(self, request: RAGRequest) -> SearchResponse:
        """Perform hybrid vector + keyword search"""
        
        # For now, use cross-domain search
        # In the future, this could combine vector and keyword search results
        return await self._cross_domain_search(request)
    
    async def _generate_response(
        self, 
        request: RAGRequest, 
        search_response: SearchResponse,
        execution_id: str
    ) -> Dict[str, Any]:
        """Generate response based on search results"""
        
        if search_response.error:
            return self._generate_error_response(search_response.error, request.domain)
        
        if not search_response.results:
            return self._generate_no_results_response(request.domain)
        
        # Check if this is an agent-enhanced result
        agent_result = next(
            (r for r in search_response.results if r.metadata.get("agent_workflow")), 
            None
        )
        
        if agent_result:
            return self._format_agent_response(agent_result, search_response, request.domain)
        
        # Generate response from search results
        if len(search_response.results) == 1:
            return self._generate_single_result_response(
                search_response.results[0], request.domain
            )
        else:
            return self._generate_multiple_results_response(
                search_response.results, request.domain
            )
    
    def _generate_single_result_response(
        self, result: SearchResult, domain: str
    ) -> Dict[str, Any]:
        """Generate response from a single search result"""
        
        domain_style = settings.DOMAIN_RESPONSE_STYLES.get(domain, settings.DOMAIN_RESPONSE_STYLES["general"])
        
        content = result.content[:settings.MAX_RESPONSE_LENGTH]
        confidence = min(result.similarity * 100, 95)  # Cap at 95%
        
        response = settings.SINGLE_RESULT_TEMPLATE.format(
            content=content,
            source_title=result.metadata.get("title", "Document"),
            confidence=int(confidence)
        )
        
        # Add domain-specific styling
        full_response = f"{domain_style['greeting']}\n\n{response}\n\n{domain_style['closing']}"
        
        return {
            "response": full_response,
            "response_type": ResponseType.DIRECT,
            "confidence": result.similarity,
            "sources": [self._format_source_info(result)],
            "source_count": 1,
            "domain_searched": domain,
            "mode_used": RAGMode.SIMPLE,
            "suggested_actions": self._generate_suggestions_for_result(result, domain),
            "related_queries": self._generate_related_queries(result)
        }
    
    def _generate_multiple_results_response(
        self, results: List[SearchResult], domain: str
    ) -> Dict[str, Any]:
        """Generate response from multiple search results"""
        
        domain_style = settings.DOMAIN_RESPONSE_STYLES.get(domain, settings.DOMAIN_RESPONSE_STYLES["general"])
        
        # Format results
        formatted_results = []
        total_confidence = 0
        
        for i, result in enumerate(results[:settings.MAX_SOURCES_TO_DISPLAY], 1):
            content = result.content[:200] + "..." if len(result.content) > 200 else result.content
            formatted_results.append(f"{i}. {content}")
            total_confidence += result.similarity
        
        avg_confidence = total_confidence / len(results)
        confidence_percent = int(min(avg_confidence * 100, 90))  # Cap at 90%
        
        response = settings.MULTIPLE_RESULTS_TEMPLATE.format(
            results="\n\n".join(formatted_results),
            source_count=len(results),
            confidence=confidence_percent
        )
        
        # Add domain-specific styling
        full_response = f"{domain_style['greeting']}\n\n{response}\n\n{domain_style['closing']}"
        
        return {
            "response": full_response,
            "response_type": ResponseType.SUMMARIZED,
            "confidence": avg_confidence,
            "sources": [self._format_source_info(r) for r in results[:settings.MAX_SOURCES_TO_DISPLAY]],
            "source_count": len(results),
            "domain_searched": domain,
            "mode_used": RAGMode.CROSS_DOMAIN,
            "suggested_actions": self._generate_suggestions_for_multiple_results(results, domain),
            "related_queries": self._generate_related_queries_from_multiple(results)
        }
    
    def _generate_no_results_response(self, domain: str) -> Dict[str, Any]:
        """Generate response when no results are found"""
        
        domain_style = settings.DOMAIN_RESPONSE_STYLES.get(domain, settings.DOMAIN_RESPONSE_STYLES["general"])
        
        suggestions = [
            "Try rephrasing your question with different keywords",
            "Check spelling and try broader terms",
            "Browse our documentation categories",
            "Contact support for personalized assistance"
        ]
        
        next_steps = [
            "Review available documentation",
            "Contact our support team",
            "Check our FAQ section"
        ]
        
        response = settings.NO_RESULTS_TEMPLATE.format(
            domain_message=domain_style["no_results"],
            suggestions="\n".join(f"- {s}" for s in suggestions),
            next_steps="\n".join(f"- {s}" for s in next_steps)
        )
        
        return {
            "response": response,
            "response_type": ResponseType.NO_RESULTS,
            "confidence": 0.0,
            "sources": [],
            "source_count": 0,
            "domain_searched": domain,
            "mode_used": RAGMode.SIMPLE,
            "suggested_actions": suggestions,
            "related_queries": []
        }
    
    def _generate_error_response(self, error: str, domain: str) -> Dict[str, Any]:
        """Generate response for error conditions"""
        
        return {
            "response": f"I encountered an issue while searching for information: {error}. Please try again or contact support.",
            "response_type": ResponseType.NO_RESULTS,
            "confidence": 0.0,
            "sources": [],
            "source_count": 0,
            "domain_searched": domain,
            "mode_used": RAGMode.SIMPLE,
            "suggested_actions": ["Try again later", "Contact support", "Rephrase your question"],
            "related_queries": []
        }
    
    def _format_agent_response(
        self, agent_result: SearchResult, search_response: SearchResponse, domain: str
    ) -> Dict[str, Any]:
        """Format response from agent workflow"""
        
        return {
            "response": agent_result.content,
            "response_type": ResponseType.GENERATED,
            "confidence": agent_result.similarity,
            "sources": [self._format_source_info(agent_result)],
            "source_count": 1,
            "domain_searched": domain,
            "mode_used": RAGMode.AGENT_ENHANCED,
            "suggested_actions": ["Follow the recommended steps", "Contact support if needed"],
            "related_queries": [],
            "agent_workflow_triggered": True,
            "agent_workflow_id": agent_result.metadata.get("workflow_id")
        }
    
    def _format_source_info(self, result: SearchResult) -> SourceInfo:
        """Format search result as source info"""
        
        return SourceInfo(
            id=result.source_id,
            title=result.metadata.get("title", "Document"),
            content=result.content[:300] + "..." if len(result.content) > 300 else result.content,
            domain=result.domain,
            similarity=result.similarity,
            metadata=result.metadata,
            url=result.metadata.get("url")
        )
    
    def _generate_suggestions_for_result(self, result: SearchResult, domain: str) -> List[str]:
        """Generate suggestions based on a single result"""
        
        suggestions = ["Ask follow-up questions for more details"]
        
        if result.metadata.get("url"):
            suggestions.append("Read the full documentation")
        
        if domain == "support":
            suggestions.append("Contact support if the issue persists")
        elif domain == "sales":
            suggestions.append("Speak with a sales representative")
        elif domain == "engineering":
            suggestions.append("Consult with the engineering team")
        
        return suggestions
    
    def _generate_suggestions_for_multiple_results(
        self, results: List[SearchResult], domain: str
    ) -> List[str]:
        """Generate suggestions based on multiple results"""
        
        return [
            "Ask for more specific information",
            "Browse related documentation",
            "Filter results by category",
            "Contact support for personalized help"
        ]
    
    def _generate_related_queries(self, result: SearchResult) -> List[str]:
        """Generate related queries from a single result"""
        
        # Simple related query generation based on metadata
        related = []
        
        if "title" in result.metadata:
            title = result.metadata["title"]
            related.append(f"Tell me more about {title}")
        
        return related[:3]
    
    def _generate_related_queries_from_multiple(self, results: List[SearchResult]) -> List[str]:
        """Generate related queries from multiple results"""
        
        domains = set(r.domain for r in results)
        related = []
        
        for domain in domains:
            related.append(f"Show me more {domain} information")
        
        return related[:3]
    
    def _generate_cache_key(self, request: RAGRequest) -> str:
        """Generate cache key for request"""
        
        key_data = f"{request.query}_{request.domain}_{request.mode}_{request.max_results}_{request.confidence_threshold}"
        return hashlib.md5(key_data.encode()).hexdigest()
    
    async def _get_cached_response(self, cache_key: str) -> Optional[Dict[str, Any]]:
        """Get cached response if available"""
        
        if not self.cache_enabled:
            return None
        
        try:
            cached = self.redis_client.get(f"rag_response:{cache_key}")
            if cached:
                import json
                return json.loads(cached)
        except Exception as e:
            logger.warning(f"Cache read error: {e}")
        
        return None
    
    async def _cache_response(self, cache_key: str, response_data: Dict[str, Any]):
        """Cache response data"""
        
        if not self.cache_enabled:
            return
        
        try:
            import json
            self.redis_client.setex(
                f"rag_response:{cache_key}",
                settings.RAG_CACHE_TTL,
                json.dumps(response_data, default=str)
            )
        except Exception as e:
            logger.warning(f"Cache write error: {e}")
    
    async def _update_source_quality(self, results: List[SearchResult], db: Session):
        """Update source quality metrics"""
        
        try:
            for result in results:
                quality = db.query(SourceQuality).filter(
                    SourceQuality.source_id == result.source_id,
                    SourceQuality.domain == result.domain
                ).first()
                
                if quality:
                    # Update existing record
                    quality.usage_count += 1
                    quality.avg_similarity = (
                        (quality.avg_similarity * (quality.usage_count - 1) + result.similarity) 
                        / quality.usage_count
                    )
                else:
                    # Create new record
                    quality = SourceQuality(
                        source_id=result.source_id,
                        domain=result.domain,
                        avg_similarity=result.similarity,
                        usage_count=1,
                        content_length=len(result.content)
                    )
                    db.add(quality)
            
            db.commit()
            
        except Exception as e:
            logger.error(f"Error updating source quality: {e}")
            db.rollback()
    
    async def close(self):
        """Close HTTP clients"""
        await self.vector_client.aclose()
        await self.agent_client.aclose()
        await self.classification_client.aclose() 
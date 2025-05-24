"""
Enhanced RAG Processor
Migrated from services/query/rag-service/src/rag_processor.py
Provides sophisticated retrieval-augmented generation with multi-mode processing
"""

import json
import uuid
import hashlib
import time
from datetime import datetime
from typing import Dict, List, Optional, Any, Union
from dataclasses import dataclass
from enum import Enum

import numpy as np
from sqlalchemy.orm import Session
from sqlalchemy import text
from sentence_transformers import SentenceTransformer

from classifiers import classifier, ClassificationResult

# Import migrated workflow modules
try:
    from workflows import BugDetectionWorkflow, FeatureRequestWorkflow, TrainingWorkflow
    from search import VectorStore, EmbeddingService
    from ingestion import FileProcessor, FileValidator
    WORKFLOWS_AVAILABLE = True
except ImportError as e:
    print(f"Warning: Some workflow modules not available: {e}")
    WORKFLOWS_AVAILABLE = False


class RAGMode(str, Enum):
    """RAG processing modes"""
    SIMPLE = "simple"
    CROSS_DOMAIN = "cross_domain"
    AGENT_ENHANCED = "agent_enhanced"
    HYBRID = "hybrid"


class ResponseType(str, Enum):
    """Response types"""
    DIRECT = "direct"
    GENERATED = "generated"
    NO_RESULTS = "no_results"
    AGENT_WORKFLOW = "agent_workflow"


@dataclass
class RAGRequest:
    """Enhanced RAG request model"""
    query: str
    domain: str = "general"
    mode: RAGMode = RAGMode.SIMPLE
    max_results: int = 5
    confidence_threshold: float = 0.3
    context: Optional[Dict] = None
    user_id: Optional[str] = None
    session_id: Optional[str] = None
    force_refresh_cache: bool = False


@dataclass
class RAGResponse:
    """Enhanced RAG response model"""
    query: str
    response: str
    intent: str
    confidence: float
    sources: List[Dict]
    domain: str
    mode_used: RAGMode
    response_type: ResponseType
    processing_time_ms: int
    execution_id: str
    source_count: int
    suggested_actions: List[str]
    related_queries: List[str]
    agent_workflow_triggered: bool = False
    agent_workflow_id: Optional[str] = None
    cache_hit: bool = False
    metadata: Dict = None


@dataclass
class SearchResult:
    """Search result model"""
    content: str
    metadata: Dict
    similarity: float
    domain: str
    source_id: str


@dataclass
class WorkflowResult:
    """Agent workflow result"""
    response: str
    confidence: float
    workflow_type: str
    workflow_id: str
    metadata: Dict
    suggested_actions: List[str]


class MultiDomainVectorStore:
    """Enhanced multi-domain vector storage and retrieval"""
    
    def __init__(self, embeddings_model: SentenceTransformer):
        self.embeddings_model = embeddings_model
        self.domain_indices = {}
        self._initialize_indices()
    
    def _initialize_indices(self):
        """Initialize FAISS indices for each domain"""
        import faiss
        
        domains = ["general", "support", "sales", "engineering", "product"]
        for domain in domains:
            # Create a new FAISS index for each domain
            index = faiss.IndexFlatIP(384)  # MiniLM dimension
            self.domain_indices[domain] = {
                "index": index,
                "metadata": [],
                "doc_ids": [],
                "last_updated": datetime.utcnow()
            }
    
    def add_embeddings(self, domain: str, embeddings: np.ndarray, metadata: List[Dict], doc_ids: List[str]):
        """Add embeddings to domain-specific index"""
        if domain not in self.domain_indices:
            self._initialize_indices()
        
        domain_data = self.domain_indices[domain]
        domain_data["index"].add(embeddings)
        domain_data["metadata"].extend(metadata)
        domain_data["doc_ids"].extend(doc_ids)
        domain_data["last_updated"] = datetime.utcnow()
    
    def search(self, query: str, domain: str, top_k: int = 5, min_similarity: float = 0.3) -> List[SearchResult]:
        """Enhanced search with filtering"""
        if domain not in self.domain_indices:
            return []
        
        domain_data = self.domain_indices[domain]
        if domain_data["index"].ntotal == 0:
            return []
        
        # Generate query embedding
        query_embedding = self.embeddings_model.encode([query])
        query_embedding = query_embedding.astype('float32')
        
        # Search in domain index
        scores, indices = domain_data["index"].search(query_embedding, min(top_k, domain_data["index"].ntotal))
        
        results = []
        for i, (score, idx) in enumerate(zip(scores[0], indices[0])):
            if idx != -1 and score >= min_similarity:  # Valid result with minimum similarity
                metadata = domain_data["metadata"][idx]
                results.append(SearchResult(
                    content=metadata.get("content", ""),
                    metadata=metadata,
                    similarity=float(score),
                    domain=domain,
                    source_id=domain_data["doc_ids"][idx]
                ))
        
        return results
    
    def cross_domain_search(self, query: str, domains: List[str], top_k: int = 10, min_similarity: float = 0.3) -> Dict[str, List[SearchResult]]:
        """Search across multiple domains with ranking"""
        all_results = {}
        
        for domain in domains:
            if domain in self.domain_indices:
                results = self.search(query, domain, top_k, min_similarity)
                if results:
                    all_results[domain] = results
        
        return all_results


class AgentWorkflowProcessor:
    """Agent workflow processing for specialized intents"""
    
    def __init__(self):
        self.workflow_handlers = {
            "bug_report": self._handle_bug_workflow,
            "feature_request": self._handle_feature_workflow,
            "training": self._handle_training_workflow
        }
    
    async def execute_workflow(
        self, 
        intent: str, 
        query: str, 
        confidence: float,
        context: Optional[Dict],
        vector_results: List[SearchResult],
        db: Session
    ) -> Optional[WorkflowResult]:
        """Execute appropriate workflow based on intent"""
        
        if intent not in self.workflow_handlers:
            return None
        
        try:
            handler = self.workflow_handlers[intent]
            result = await handler(query, confidence, context, vector_results, db)
            return result
        except Exception as e:
            print(f"Workflow execution failed for {intent}: {e}")
            return None
    
    async def _handle_bug_workflow(
        self, 
        query: str, 
        confidence: float,
        context: Optional[Dict],
        vector_results: List[SearchResult],
        db: Session
    ) -> WorkflowResult:
        """Handle bug detection workflow"""
        
        workflow_id = str(uuid.uuid4())
        
        # Analyze error patterns
        error_patterns = self._extract_error_patterns(query)
        
        # Search for known issues
        known_issues = await self._search_known_issues(query, db)
        
        # Generate bug analysis
        analysis = self._generate_bug_analysis(query, error_patterns, known_issues, vector_results)
        
        # Generate response
        response = self._format_bug_response(analysis, known_issues, vector_results)
        
        # Store workflow execution
        await self._store_workflow_execution(
            db, workflow_id, "bug_report", query, response, analysis
        )
        
        return WorkflowResult(
            response=response,
            confidence=min(confidence + 0.1, 0.95),  # Boost confidence for workflow
            workflow_type="bug_report",
            workflow_id=workflow_id,
            metadata=analysis,
            suggested_actions=[
                "Check application logs for detailed error information",
                "Verify system configuration and dependencies",
                "Test in a controlled environment to reproduce the issue",
                "Contact support team with detailed error logs"
            ]
        )
    
    async def _handle_feature_workflow(
        self, 
        query: str, 
        confidence: float,
        context: Optional[Dict],
        vector_results: List[SearchResult],
        db: Session
    ) -> WorkflowResult:
        """Handle feature request workflow"""
        
        workflow_id = str(uuid.uuid4())
        
        # Search for existing features
        existing_features = await self._search_existing_features(query, vector_results, db)
        
        # Analyze request
        analysis = self._generate_feature_analysis(query, existing_features, vector_results)
        
        # Generate response
        response = self._format_feature_response(analysis, existing_features)
        
        # Store workflow execution
        await self._store_workflow_execution(
            db, workflow_id, "feature_request", query, response, analysis
        )
        
        return WorkflowResult(
            response=response,
            confidence=min(confidence + 0.05, 0.9),
            workflow_type="feature_request",
            workflow_id=workflow_id,
            metadata=analysis,
            suggested_actions=[
                "Check our roadmap for planned features",
                "Submit a formal feature request",
                "Contact the product team for prioritization",
                "Consider available workarounds"
            ]
        )
    
    async def _handle_training_workflow(
        self, 
        query: str, 
        confidence: float,
        context: Optional[Dict],
        vector_results: List[SearchResult],
        db: Session
    ) -> WorkflowResult:
        """Handle training/documentation workflow"""
        
        workflow_id = str(uuid.uuid4())
        
        # Process documentation results
        doc_analysis = self._generate_training_analysis(query, vector_results)
        
        # Generate step-by-step guide
        response = self._format_training_response(doc_analysis, vector_results)
        
        # Store workflow execution
        await self._store_workflow_execution(
            db, workflow_id, "training", query, response, doc_analysis
        )
        
        return WorkflowResult(
            response=response,
            confidence=min(confidence + 0.15, 0.95),  # High confidence for training
            workflow_type="training",
            workflow_id=workflow_id,
            metadata=doc_analysis,
            suggested_actions=[
                "Review the linked documentation",
                "Try the suggested approach",
                "Practice with examples",
                "Contact support if you need further assistance"
            ]
        )
    
    def _extract_error_patterns(self, query: str) -> Dict[str, Any]:
        """Extract error patterns from query"""
        import re
        
        patterns = {
            "stack_trace": bool(re.search(r"(stack trace|traceback|exception)", query.lower())),
            "error_codes": re.findall(r"\b[45]\d{2}\b", query),  # HTTP error codes
            "error_keywords": [word for word in ["error", "exception", "fail", "crash", "bug"] if word in query.lower()],
            "severity_indicators": [word for word in ["critical", "urgent", "blocking", "minor"] if word in query.lower()]
        }
        
        return patterns
    
    async def _search_known_issues(self, query: str, db: Session) -> List[Dict]:
        """Search for known issues in database"""
        try:
            # This would search a known_issues table
            result = db.execute(
                text("""
                    SELECT title, description, solution, severity 
                    FROM known_issues 
                    WHERE LOWER(description) LIKE LOWER(:query) 
                    OR LOWER(title) LIKE LOWER(:query)
                    LIMIT 5
                """),
                {"query": f"%{query}%"}
            )
            return [{"title": row.title, "description": row.description, "solution": row.solution, "severity": row.severity} for row in result.fetchall()]
        except:
            return []
    
    async def _search_existing_features(self, query: str, vector_results: List[SearchResult], db: Session) -> List[Dict]:
        """Search for existing features"""
        # Analyze vector results for features
        features = []
        for result in vector_results:
            if any(keyword in result.content.lower() for keyword in ["feature", "functionality", "capability"]):
                features.append({
                    "title": result.metadata.get("title", "Feature"),
                    "description": result.content[:200],
                    "domain": result.domain
                })
        
        return features[:3]  # Top 3 features
    
    def _generate_bug_analysis(self, query: str, error_patterns: Dict, known_issues: List[Dict], vector_results: List[SearchResult]) -> Dict:
        """Generate comprehensive bug analysis"""
        
        severity = "medium"
        if error_patterns["severity_indicators"]:
            if any(word in error_patterns["severity_indicators"] for word in ["critical", "urgent", "blocking"]):
                severity = "high"
            elif "minor" in error_patterns["severity_indicators"]:
                severity = "low"
        
        return {
            "severity": severity,
            "error_patterns": error_patterns,
            "known_issues_count": len(known_issues),
            "has_stack_trace": error_patterns["stack_trace"],
            "error_codes": error_patterns["error_codes"],
            "similar_results_count": len(vector_results)
        }
    
    def _generate_feature_analysis(self, query: str, existing_features: List[Dict], vector_results: List[SearchResult]) -> Dict:
        """Generate feature request analysis"""
        return {
            "existing_features_count": len(existing_features),
            "similar_requests_count": len(vector_results),
            "request_type": "enhancement" if "improve" in query.lower() or "enhance" in query.lower() else "new_feature"
        }
    
    def _generate_training_analysis(self, query: str, vector_results: List[SearchResult]) -> Dict:
        """Generate training content analysis"""
        return {
            "documentation_count": len(vector_results),
            "query_type": "how_to" if "how" in query.lower() else "what_is" if "what" in query.lower() else "general",
            "complexity": "beginner" if any(word in query.lower() for word in ["basic", "simple", "intro"]) else "advanced"
        }
    
    def _format_bug_response(self, analysis: Dict, known_issues: List[Dict], vector_results: List[SearchResult]) -> str:
        """Format bug workflow response"""
        response = f"**Bug Analysis Report**\n\n"
        response += f"**Severity**: {analysis['severity'].title()}\n\n"
        
        if known_issues:
            response += f"**Known Issues Found**: {len(known_issues)}\n"
            for issue in known_issues[:2]:  # Top 2
                response += f"- {issue['title']}: {issue['solution'][:100]}...\n"
            response += "\n"
        
        if analysis["error_patterns"]["error_codes"]:
            response += f"**Error Codes Detected**: {', '.join(analysis['error_patterns']['error_codes'])}\n\n"
        
        if vector_results:
            response += f"**Related Documentation**: {len(vector_results)} relevant documents found\n\n"
        
        response += "**Next Steps**:\n"
        response += "1. Review the identified solutions\n"
        response += "2. Check system logs for additional details\n"
        response += "3. Test proposed fixes in a safe environment\n"
        
        return response
    
    def _format_feature_response(self, analysis: Dict, existing_features: List[Dict]) -> str:
        """Format feature workflow response"""
        response = f"**Feature Request Analysis**\n\n"
        response += f"**Request Type**: {analysis['request_type'].replace('_', ' ').title()}\n\n"
        
        if existing_features:
            response += f"**Existing Related Features**:\n"
            for feature in existing_features:
                response += f"- {feature['title']}: {feature['description'][:100]}...\n"
            response += "\n"
        
        response += "**Status**: Under review\n\n"
        response += "**Next Steps**:\n"
        response += "1. Review existing related features\n"
        response += "2. Submit formal feature request\n"
        response += "3. Contact product team for prioritization\n"
        
        return response
    
    def _format_training_response(self, analysis: Dict, vector_results: List[SearchResult]) -> str:
        """Format training workflow response"""
        response = f"**Training & Documentation**\n\n"
        response += f"**Query Type**: {analysis['query_type'].replace('_', ' ').title()}\n"
        response += f"**Complexity Level**: {analysis['complexity'].title()}\n\n"
        
        if vector_results:
            response += f"**Available Resources**: {len(vector_results)} documents found\n\n"
            response += "**Key Information**:\n"
            for i, result in enumerate(vector_results[:3], 1):
                title = result.metadata.get("title", f"Document {i}")
                response += f"{i}. **{title}**: {result.content[:150]}...\n\n"
        
        response += "**Recommended Learning Path**:\n"
        response += "1. Start with the provided resources\n"
        response += "2. Practice with examples\n"
        response += "3. Ask follow-up questions if needed\n"
        
        return response
    
    async def _store_workflow_execution(
        self, 
        db: Session, 
        workflow_id: str, 
        workflow_type: str, 
        query: str, 
        response: str, 
        analysis: Dict
    ):
        """Store workflow execution in database"""
        try:
            db.execute(
                text("""
                    INSERT INTO workflow_executions (
                        id, workflow_type, query, response, analysis, created_at
                    ) VALUES (
                        :id, :workflow_type, :query, :response, :analysis, :created_at
                    )
                """),
                {
                    "id": workflow_id,
                    "workflow_type": workflow_type,
                    "query": query,
                    "response": response,
                    "analysis": json.dumps(analysis),
                    "created_at": datetime.utcnow()
                }
            )
            db.commit()
        except Exception as e:
            print(f"Failed to store workflow execution: {e}")
            db.rollback()


class EnhancedRAGProcessor:
    """Enhanced RAG processor with multi-mode processing and agent workflows"""
    
    def __init__(self, embeddings_model: SentenceTransformer):
        self.embeddings_model = embeddings_model
        self.vector_store = MultiDomainVectorStore(embeddings_model)
        self.agent_processor = AgentWorkflowProcessor()
        self.response_cache = {}  # Simple in-memory cache
        self.response_templates = self._load_response_templates()
    
    def _load_response_templates(self) -> Dict[str, str]:
        """Load enhanced response templates"""
        return {
            "bug_report": """**Bug Analysis Report**

{agent_response}

**Confidence**: {confidence}%
**Processing Mode**: {mode}

**Sources**:
{sources}""",

            "feature_request": """**Feature Request Analysis**

{agent_response}

**Confidence**: {confidence}%
**Processing Mode**: {mode}

**Related Information**:
{sources}""",

            "training": """**Training & Documentation**

{agent_response}

**Confidence**: {confidence}%
**Processing Mode**: {mode}

**Resources**:
{sources}""",

            "general_query": """Based on your query, here's the relevant information:

{context}

**Confidence**: {confidence}%
**Processing Mode**: {mode}

**Sources**:
{sources}"""
        }
    
    async def process_query(self, request: RAGRequest, db: Session) -> RAGResponse:
        """Enhanced query processing with multi-mode support"""
        start_time = time.time()
        execution_id = str(uuid.uuid4())
        
        # Check cache first
        cache_key = self._generate_cache_key(request)
        if not request.force_refresh_cache and cache_key in self.response_cache:
            cached_response = self.response_cache[cache_key]
            cached_response.cache_hit = True
            cached_response.execution_id = execution_id
            return cached_response
        
        try:
            # Step 1: Intent Classification
            classification_result = await classifier.classify_query(
                query=request.query,
                domain=request.domain,
                context=request.context,
                db=db
            )
            
            # Step 2: Retrieve documents based on mode
            search_results = await self._perform_search(request, classification_result)
            
            # Step 3: Agent workflow processing (if applicable)
            agent_result = None
            if (request.mode == RAGMode.AGENT_ENHANCED and 
                classification_result.confidence > 0.7 and 
                classification_result.intent in ["bug_report", "feature_request", "training"]):
                
                agent_result = await self.agent_processor.execute_workflow(
                    intent=classification_result.intent,
                    query=request.query,
                    confidence=classification_result.confidence,
                    context=request.context,
                    vector_results=search_results,
                    db=db
                )
            
            # Step 4: Generate response
            response_data = self._generate_enhanced_response(
                request, classification_result, search_results, agent_result
            )
            
            # Step 5: Create response object
            processing_time = int((time.time() - start_time) * 1000)
            
            rag_response = RAGResponse(
                query=request.query,
                response=response_data["response"],
                intent=classification_result.intent,
                confidence=response_data["confidence"],
                sources=response_data["sources"],
                domain=request.domain,
                mode_used=request.mode,
                response_type=response_data["response_type"],
                processing_time_ms=processing_time,
                execution_id=execution_id,
                source_count=len(response_data["sources"]),
                suggested_actions=response_data.get("suggested_actions", []),
                related_queries=response_data.get("related_queries", []),
                agent_workflow_triggered=agent_result is not None,
                agent_workflow_id=agent_result.workflow_id if agent_result else None,
                metadata=response_data.get("metadata", {})
            )
            
            # Cache the response
            self.response_cache[cache_key] = rag_response
            
            # Store execution in database
            await self._store_execution(db, request, rag_response, classification_result)
            
            return rag_response
            
        except Exception as e:
            print(f"Error in RAG processing: {e}")
            return self._generate_error_response(request, str(e), execution_id, int((time.time() - start_time) * 1000))
    
    async def _perform_search(self, request: RAGRequest, classification: ClassificationResult) -> List[SearchResult]:
        """Perform search based on mode"""
        
        if request.mode == RAGMode.SIMPLE:
            return self.vector_store.search(
                request.query, 
                request.domain, 
                request.max_results, 
                request.confidence_threshold
            )
        
        elif request.mode == RAGMode.CROSS_DOMAIN:
            # Search across all domains
            all_domains = ["general", "support", "sales", "engineering", "product"]
            cross_results = self.vector_store.cross_domain_search(
                request.query, 
                all_domains, 
                request.max_results * 2, 
                request.confidence_threshold
            )
            
            # Flatten and rank results
            all_results = []
            for domain, results in cross_results.items():
                all_results.extend(results)
            
            # Sort by similarity and return top results
            return sorted(all_results, key=lambda x: x.similarity, reverse=True)[:request.max_results]
        
        elif request.mode in [RAGMode.AGENT_ENHANCED, RAGMode.HYBRID]:
            # Use cross-domain search as base for agent processing
            all_domains = ["general", request.domain]  # Focus on relevant domains
            cross_results = self.vector_store.cross_domain_search(
                request.query, 
                all_domains, 
                request.max_results, 
                request.confidence_threshold
            )
            
            all_results = []
            for domain, results in cross_results.items():
                all_results.extend(results)
            
            return sorted(all_results, key=lambda x: x.similarity, reverse=True)[:request.max_results]
        
        else:
            # Default to simple search
            return self.vector_store.search(
                request.query, 
                request.domain, 
                request.max_results, 
                request.confidence_threshold
            )
    
    def _generate_enhanced_response(
        self,
        request: RAGRequest,
        classification: ClassificationResult,
        search_results: List[SearchResult],
        agent_result: Optional[WorkflowResult]
    ) -> Dict[str, Any]:
        """Generate enhanced response with agent integration"""
        
        # If agent workflow was triggered, use its response
        if agent_result:
            return {
                "response": agent_result.response,
                "confidence": agent_result.confidence,
                "response_type": ResponseType.AGENT_WORKFLOW,
                "sources": self._format_sources(search_results),
                "suggested_actions": agent_result.suggested_actions,
                "related_queries": self._generate_related_queries(search_results),
                "metadata": agent_result.metadata
            }
        
        # Standard response generation
        if not search_results:
            return self._generate_no_results_response(request.domain)
        
        # Format sources
        sources = self._format_sources(search_results)
        
        # Generate context from results
        context = self._generate_context(search_results)
        
        # Select template and generate response
        template = self.response_templates.get(classification.intent, self.response_templates["general_query"])
        
        response = template.format(
            context=context,
            confidence=int(classification.confidence * 100),
            mode=request.mode.value,
            sources="\n".join([f"- {s['title']}" for s in sources])
        )
        
        return {
            "response": response,
            "confidence": classification.confidence,
            "response_type": ResponseType.GENERATED,
            "sources": sources,
            "suggested_actions": self._generate_suggested_actions(classification.intent),
            "related_queries": self._generate_related_queries(search_results),
            "metadata": {"classification": classification.metadata}
        }
    
    def _format_sources(self, results: List[SearchResult]) -> List[Dict]:
        """Format search results as sources"""
        sources = []
        for result in results:
            sources.append({
                "id": result.source_id,
                "title": result.metadata.get("title", "Document"),
                "content": result.content[:200] + "..." if len(result.content) > 200 else result.content,
                "domain": result.domain,
                "similarity": result.similarity,
                "url": result.metadata.get("url")
            })
        return sources
    
    def _generate_context(self, results: List[SearchResult]) -> str:
        """Generate context from search results"""
        if not results:
            return "No relevant information found."
        
        context_parts = []
        for result in results[:3]:  # Top 3 results
            context_parts.append(result.content[:300])
        
        return "\n\n".join(context_parts)
    
    def _generate_suggested_actions(self, intent: str) -> List[str]:
        """Generate suggested actions based on intent"""
        actions = {
            "bug_report": [
                "Check application logs",
                "Verify system configuration",
                "Test in controlled environment",
                "Contact support with details"
            ],
            "feature_request": [
                "Check product roadmap",
                "Submit formal request",
                "Consider alternatives",
                "Contact product team"
            ],
            "training": [
                "Review documentation",
                "Practice with examples",
                "Try step-by-step guide",
                "Ask follow-up questions"
            ],
            "general": [
                "Review provided information",
                "Try related resources",
                "Refine your question",
                "Contact support if needed"
            ]
        }
        return actions.get(intent, actions["general"])
    
    def _generate_related_queries(self, results: List[SearchResult]) -> List[str]:
        """Generate related queries based on results"""
        # Simple related query generation based on metadata
        queries = []
        for result in results[:2]:
            title = result.metadata.get("title", "")
            if title:
                queries.append(f"Tell me more about {title}")
        
        return queries
    
    def _generate_no_results_response(self, domain: str) -> Dict[str, Any]:
        """Generate response when no results found"""
        return {
            "response": f"I couldn't find specific information for your query in the {domain} domain. Try rephrasing your question or checking other domains.",
            "confidence": 0.0,
            "response_type": ResponseType.NO_RESULTS,
            "sources": [],
            "suggested_actions": [
                "Try rephrasing your question",
                "Use different keywords",
                "Check other domains",
                "Contact support for assistance"
            ],
            "related_queries": [],
            "metadata": {}
        }
    
    def _generate_error_response(self, request: RAGRequest, error: str, execution_id: str, processing_time: int) -> RAGResponse:
        """Generate error response"""
        return RAGResponse(
            query=request.query,
            response=f"I encountered an error processing your request: {error}. Please try again.",
            intent="error",
            confidence=0.0,
            sources=[],
            domain=request.domain,
            mode_used=request.mode,
            response_type=ResponseType.NO_RESULTS,
            processing_time_ms=processing_time,
            execution_id=execution_id,
            source_count=0,
            suggested_actions=["Try again", "Rephrase question", "Contact support"],
            related_queries=[],
            metadata={"error": error}
        )
    
    def _generate_cache_key(self, request: RAGRequest) -> str:
        """Generate cache key for request"""
        key_data = f"{request.query}:{request.domain}:{request.mode}:{request.max_results}:{request.confidence_threshold}"
        return hashlib.md5(key_data.encode()).hexdigest()
    
    async def _store_execution(
        self,
        db: Session,
        request: RAGRequest,
        response: RAGResponse,
        classification: ClassificationResult
    ):
        """Store execution in database"""
        try:
            db.execute(
                text("""
                    INSERT INTO rag_executions (
                        id, query, domain, mode, intent, confidence, 
                        response_type, source_count, processing_time_ms, 
                        user_id, session_id, created_at
                    ) VALUES (
                        :id, :query, :domain, :mode, :intent, :confidence,
                        :response_type, :source_count, :processing_time_ms,
                        :user_id, :session_id, :created_at
                    )
                """),
                {
                    "id": response.execution_id,
                    "query": request.query,
                    "domain": request.domain,
                    "mode": request.mode.value,
                    "intent": classification.intent,
                    "confidence": classification.confidence,
                    "response_type": response.response_type.value,
                    "source_count": response.source_count,
                    "processing_time_ms": response.processing_time_ms,
                    "user_id": request.user_id,
                    "session_id": request.session_id,
                    "created_at": datetime.utcnow()
                }
            )
            db.commit()
        except Exception as e:
            print(f"Failed to store RAG execution: {e}")
            db.rollback()
    
    async def get_analytics(self, db: Session, domain: Optional[str] = None, days: int = 7) -> Dict:
        """Get RAG analytics"""
        try:
            where_clause = "WHERE created_at >= NOW() - INTERVAL '%s days'" % days
            if domain:
                where_clause += f" AND domain = '{domain}'"
            
            # Mode distribution
            mode_stats = db.execute(
                text(f"""
                    SELECT mode, COUNT(*) as count, AVG(confidence) as avg_confidence
                    FROM rag_executions
                    {where_clause}
                    GROUP BY mode
                """)
            ).fetchall()
            
            # Intent distribution
            intent_stats = db.execute(
                text(f"""
                    SELECT intent, COUNT(*) as count, AVG(processing_time_ms) as avg_time
                    FROM rag_executions
                    {where_clause}
                    GROUP BY intent
                """)
            ).fetchall()
            
            return {
                "mode_distribution": [
                    {"mode": row.mode, "count": row.count, "avg_confidence": float(row.avg_confidence)}
                    for row in mode_stats
                ],
                "intent_distribution": [
                    {"intent": row.intent, "count": row.count, "avg_time": float(row.avg_time)}
                    for row in intent_stats
                ]
            }
        except Exception:
            return {"mode_distribution": [], "intent_distribution": []}


# Global instances
rag_processor = None

def initialize_rag_processor(embeddings_model: SentenceTransformer):
    """Initialize the global RAG processor"""
    global rag_processor
    rag_processor = EnhancedRAGProcessor(embeddings_model)
    return rag_processor 
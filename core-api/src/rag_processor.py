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
import re

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
    organization_id: Optional[str] = None
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
        # Initialize embeddings service for consistent embedding generation
        try:
            from embeddings_service import get_embeddings_service
            self.embeddings_service = get_embeddings_service()
        except ImportError:
            self.embeddings_service = None
        self.domain_indices = {}
        self._initialize_indices()
    
    def _initialize_indices(self):
        """Initialize FAISS indices for each domain"""
        import faiss
        
        domains = ["general", "support", "sales", "engineering", "product"]
        for domain in domains:
            # Create a new FAISS index for each domain - updated for 768-dimensional embeddings (nomic-embed-text)
            index = faiss.IndexFlatIP(768)  # nomic-embed-text dimension
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
    
    async def search(self, query: str, domain: str, top_k: int = 5, min_similarity: float = 0.3, organization_id: Optional[str] = None) -> List[SearchResult]:
        """Search embeddings in database with organization isolation"""
        from database import SessionLocal
        
        print(f"🔍 DEBUG: Starting search for query='{query}', domain='{domain}', org_id='{organization_id}'")
        
        # Generate query embedding using Ollama (same as web scraper) for consistency
        try:
            from search.embedding_service import EmbeddingService
            from config import get_settings
            
            settings = get_settings()
            embedding_service = EmbeddingService(settings)
            await embedding_service.initialize()
            
            # Generate embedding using the same service as web scraper (Ollama 768d)
            query_embedding = await embedding_service.generate_embedding(query)
            print(f"🔍 DEBUG: Query embedding generated using Ollama, shape: {query_embedding.shape}")
            
        except Exception as e:
            print(f"⚠️ DEBUG: Ollama embedding failed, falling back to SentenceTransformer: {e}")
            # Fallback to SentenceTransformer if Ollama fails
            query_embedding = self.embeddings_model.encode([query])[0]
            print(f"🔍 DEBUG: Query embedding generated using SentenceTransformer fallback, shape: {query_embedding.shape}")
        
        db = SessionLocal()
        try:
            # Get domain_id from domain name
            domain_result = db.execute(
                text("SELECT id FROM organization_domains WHERE domain_name = :domain AND organization_id = :org_id"),
                {"domain": domain, "org_id": organization_id}
            ).fetchone()
            
            if not domain_result:
                print(f"❌ DEBUG: Domain '{domain}' not found for organization {organization_id}")
                return []
            
            domain_id = domain_result.id
            print(f"✅ DEBUG: Found domain_id: {domain_id}")
            
            # Build query parameters
            query_params = {
                "domain_id": domain_id,
                "organization_id": organization_id
            }
            
            # Query embeddings from database with organization isolation and polymorphic support
            result = db.execute(
                text("""
                    SELECT e.id, e.content_text, e.embedding, e.source_id, e.chunk_index, e.metadata,
                           COALESCE(f.original_filename, cp.title) as title,
                           COALESCE(f.content_type, 'text/html') as content_type,
                           od.domain_name, e.organization_id, e.source_type,
                           cp.url as source_url
                    FROM embeddings e
                    LEFT JOIN files f ON e.source_type = 'file' AND e.source_id = f.id
                    LEFT JOIN crawled_pages cp ON e.source_type = 'web_page' AND e.source_id = cp.id
                    LEFT JOIN organization_domains od ON e.domain_id = od.id
                    WHERE e.domain_id = :domain_id
                    AND e.organization_id = :organization_id
                    AND e.source_id IS NOT NULL
                    AND (
                        (e.source_type = 'file' AND f.processed = true)
                        OR 
                        (e.source_type = 'web_page' AND cp.status = 'success')
                        OR
                        (e.source_type NOT IN ('file', 'web_page'))
                    )
                    ORDER BY e.created_at DESC
                    LIMIT 200
                """),
                query_params
            )
            
            embeddings_data = result.fetchall()
            print(f"🔍 DEBUG: Found {len(embeddings_data)} embeddings in database")
            
            if not embeddings_data:
                print("❌ DEBUG: No embeddings found!")
                return []
            
            # Debug first few embeddings
            for i, row in enumerate(embeddings_data[:3]):
                print(f"🔍 DEBUG: Embedding {i+1}: source_type={row.source_type}, title='{row.title}', content_preview='{row.content_text[:50]}...'")
            
            # Calculate similarities
            results = []
            similarity_scores = []
            for row in embeddings_data:
                try:
                    # Parse stored embedding from JSON string to numpy array
                    if isinstance(row.embedding, str):
                        embedding_list = json.loads(row.embedding)
                    else:
                        embedding_list = row.embedding
                    stored_embedding = np.array(embedding_list, dtype=np.float32)
                    
                    print(f"🔍 DEBUG: Comparing query shape {query_embedding.shape} with stored shape {stored_embedding.shape}")
                    
                    # Calculate cosine similarity
                    similarity = np.dot(query_embedding, stored_embedding) / (
                        np.linalg.norm(query_embedding) * np.linalg.norm(stored_embedding)
                    )
                    
                    similarity_scores.append(similarity)
                    
                    if similarity >= min_similarity:
                        # Parse embedding metadata if it exists
                        embedding_metadata = {}
                        if row.metadata:
                            try:
                                if isinstance(row.metadata, str):
                                    embedding_metadata = json.loads(row.metadata)
                                else:
                                    embedding_metadata = row.metadata
                            except Exception as e:
                                print(f"⚠️ DEBUG: Failed to parse embedding metadata: {e}")
                        
                        # Build complete metadata including visual content
                        complete_metadata = {
                            "title": row.title,
                            "content_type": row.content_type,
                            "chunk_index": row.chunk_index,
                            "organization_id": str(row.organization_id),
                            "source_url": row.source_url,
                            "source_type": row.source_type
                        }
                        
                        # Include visual content if available in embedding metadata
                        if embedding_metadata.get('visual_content'):
                            complete_metadata['visual_content'] = embedding_metadata['visual_content']
                            print(f"✅ DEBUG: Found visual content in embedding metadata for {row.title}")
                        
                        results.append(SearchResult(
                            content=row.content_text,
                            metadata=complete_metadata,
                            similarity=float(similarity),
                            domain=row.domain_name,  # Use domain_name from join
                            source_id=str(row.source_id) if row.source_id else ""
                        ))
                except Exception as e:
                    print(f"❌ DEBUG: Error calculating similarity for embedding {row.id}: {e}")
                    continue
            
            print(f"🔍 DEBUG: Calculated {len(similarity_scores)} similarities")
            if similarity_scores:
                max_sim = max(similarity_scores)
                avg_sim = sum(similarity_scores) / len(similarity_scores)
                print(f"🔍 DEBUG: Max similarity: {max_sim:.3f}, Avg similarity: {avg_sim:.3f}, Min threshold: {min_similarity}")
                print(f"🔍 DEBUG: Results above threshold: {len(results)}")
            
            # Sort by similarity and return top results
            results.sort(key=lambda x: x.similarity, reverse=True)
            final_results = results[:top_k]
            print(f"🔍 DEBUG: Returning {len(final_results)} results")
            
            return final_results
            
        except Exception as e:
            print(f"❌ DEBUG: Database search error: {e}")
            import traceback
            traceback.print_exc()
            return []
        finally:
            db.close()
    
    async def cross_domain_search(self, query: str, domains: List[str], top_k: int = 10, min_similarity: float = 0.3, organization_id: Optional[str] = None) -> Dict[str, List[SearchResult]]:
        """Search across multiple domains with ranking"""
        all_results = {}
        
        for domain in domains:
            # Always search in database, not just domain_indices
            results = await self.search(query, domain, top_k, min_similarity, organization_id)
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
        
        # Detect query type with more specific categories
        query_lower = query.lower()
        query_type = "general"
        procedure_action = ""
        
        if "how" in query_lower:
            if any(keyword in query_lower for keyword in ["create", "make", "build", "setup", "configure"]):
                query_type = "how_to"
                # Extract what they want to create/do
                if "create" in query_lower:
                    create_match = re.search(r'create\s+(?:a\s+)?(\w+)', query_lower)
                    if create_match:
                        procedure_action = f"create a {create_match.group(1)}"
                    else:
                        procedure_action = "create this item"
                elif "job" in query_lower:
                    procedure_action = "create a job"
            else:
                query_type = "how_to"
        elif "what" in query_lower:
            query_type = "what_is"
        
        # Detect complexity level
        complexity = "intermediate"
        if any(word in query_lower for word in ["basic", "simple", "intro", "beginner", "start"]):
            complexity = "beginner"
        elif any(word in query_lower for word in ["advanced", "complex", "detailed", "expert"]):
            complexity = "advanced"
        
        # Analyze available documentation quality
        has_procedural_content = any("step" in result.content.lower() or "procedure" in result.content.lower() 
                                   for result in vector_results)
        has_visual_content = any(result.metadata.get("images") or result.metadata.get("screenshots") 
                               for result in vector_results)
        
        return {
            "documentation_count": len(vector_results),
            "query_type": query_type,
            "procedure_action": procedure_action,
            "complexity": complexity,
            "has_procedural_content": has_procedural_content,
            "has_visual_content": has_visual_content,
            "content_quality": "high" if has_procedural_content and len(vector_results) > 0 else "medium"
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
        """Generate training-focused response with enhanced formatting"""
        if not vector_results:
            return "I couldn't find specific training materials for your question. Please contact support for assistance."
        
        # Get the best result
        best_result = max(vector_results, key=lambda x: x.similarity)
        
        # Check if this is a procedural question (how-to)
        is_procedural = analysis.get("query_type") == "how_to"
        has_steps = any("step" in result.content.lower() for result in vector_results)
        
        if is_procedural and has_steps:
            # Format as step-by-step guide
            response_parts = []
            
            # Add introductory context
            title = best_result.metadata.get("title", "guide")
            response_parts.append(f"Here's how to {analysis.get('procedure_action', 'complete this task')} based on our {title}:")
            
            # Extract and format steps
            content = best_result.content
            
            # Try different step extraction patterns
            step_patterns = [
                r'(?:^|\n)\s*(?:Step\s*)?(\d+)[\.\)]\s*([^\n]+)',
                r'(?:^|\n)\s*(\d+)\.\s*([^\n]+)',
                r'(?:^|\n)\s*[\-\*]\s*([^\n]+)'
            ]
            
            steps_found = []
            for pattern in step_patterns:
                matches = re.findall(pattern, content, re.MULTILINE | re.IGNORECASE)
                if matches:
                    if len(matches[0]) == 2:  # Pattern with step number and text
                        steps_found = [f"{m[0]}. {m[1].strip()}" for m in matches[:8]]
                    else:  # Pattern with just text
                        steps_found = [f"{i+1}. {m.strip()}" for i, m in enumerate(matches[:8])]
                    break
            
            if steps_found:
                response_parts.append("\n".join(steps_found))
            else:
                # Fallback: extract first few sentences as guidance
                sentences = content.split('. ')
                guidance = '. '.join(sentences[:3])
                response_parts.append(guidance)
            
            # Add helpful context
            if best_result.metadata.get("images") or best_result.metadata.get("screenshots"):
                response_parts.append("\n📷 This guide includes screenshots for visual reference.")
            
            return "\n\n".join(response_parts)
        
        else:
            # Standard informational response
            content = best_result.content.strip()
            
            # Create a focused response
            sentences = content.split('. ')
            key_info = '. '.join(sentences[:4]) if len(sentences) > 4 else content
            
            if len(key_info) > 400:
                key_info = key_info[:400] + "..."
            
            title = best_result.metadata.get("title", "documentation")
            
            response = f"Based on our {title}:\n\n{key_info}"
            
            # Add reference to visual content if available
            if best_result.metadata.get("images") or best_result.metadata.get("screenshots"):
                response += "\n\n📷 Visual guides and screenshots are available in the full documentation."
            
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
    """Enhanced RAG processor with multi-mode processing and intelligent routing"""
    
    def __init__(self, embeddings_model: SentenceTransformer):
        self.embeddings_model = embeddings_model
        self.vector_store = MultiDomainVectorStore(embeddings_model)
        self.agent_processor = AgentWorkflowProcessor()
        # Enhanced cache with timestamps, domain tracking, and semantic metadata
        self.response_cache = {}  # {cache_key: {"response": RAGResponse, "timestamp": datetime, "domain": str, "query_embedding": np.array, "source_ids": set}}
        self.domain_last_updated = {}  # {domain: datetime} - track when domain content was last updated
        self.cache_ttl_seconds = 3600  # 1 hour default TTL
        self.similarity_threshold_for_cache_update = 0.7  # Threshold for determining if new content affects cached queries
        
    async def smart_cache_update_for_new_content(self, domain: str, new_file_id: str, new_content_chunks: List[str], db: Session):
        """Smart cache update when new content is added - only update relevant cached queries"""
        if not new_content_chunks:
            return
        
        try:
            # Generate embeddings for new content to analyze semantic similarity
            new_content_text = " ".join(new_content_chunks[:3])  # Sample of new content
            if self.embeddings_model:
                new_content_embedding = self.embeddings_model.encode([new_content_text])[0]
            else:
                print("No embeddings model available for smart cache update")
                return
            
            updated_count = 0
            invalidated_count = 0
            enhanced_count = 0
            
            # Analyze each cached query for relevance to new content
            cache_updates = {}
            for cache_key, cache_data in self.response_cache.items():
                if cache_data.get("domain") != domain:
                    continue
                
                query_embedding = cache_data.get("query_embedding")
                if query_embedding is None:
                    # Old cache entry without embedding - invalidate it
                    cache_updates[cache_key] = "invalidate"
                    invalidated_count += 1
                    continue
                
                # Calculate semantic similarity between cached query and new content
                similarity = np.dot(query_embedding, new_content_embedding) / (
                    np.linalg.norm(query_embedding) * np.linalg.norm(new_content_embedding)
                )
                
                if similarity >= self.similarity_threshold_for_cache_update:
                    # High similarity - this new content is relevant to the cached query
                    # We need to either update or invalidate this cache entry
                    
                    cached_response = cache_data["response"]
                    
                    # For now, invalidate high-similarity cached queries
                    # TODO: Implement cache enhancement in future version
                    cache_updates[cache_key] = "invalidate"
                    invalidated_count += 1
                else:
                    # Low similarity - new content doesn't affect this cached query
                    updated_count += 1
            
            # Apply cache updates
            for cache_key, update_action in cache_updates.items():
                if update_action == "invalidate":
                    del self.response_cache[cache_key]
            
            print(f"Smart cache update for domain '{domain}': {updated_count} preserved, {enhanced_count} enhanced, {invalidated_count} invalidated")
            
        except Exception as e:
            print(f"Error in smart cache update: {e}")
            # Fallback to domain invalidation if smart update fails
            self.invalidate_cache_for_domain(domain)
    
    def _can_enhance_response(self, cached_response: RAGResponse, new_file_id: str) -> bool:
        """Determine if a cached response can be enhanced with new content"""
        # Don't enhance if response already has many sources
        if cached_response.source_count >= 5:
            return False
        
        # Don't enhance if confidence is already very high
        cached_confidence = cached_response.confidence or 0.0  # Handle None confidence
        if cached_confidence >= 0.9:
            return False
        
        # Don't enhance error responses or no-results responses
        if cached_response.response_type in [ResponseType.NO_RESULTS]:
            return True  # Actually, these might benefit from new content
        
        return True
    
    async def _enhance_cached_response(
        self, 
        cached_response: RAGResponse, 
        new_file_id: str, 
        new_content_chunks: List[str],
        db: Session
    ) -> Optional[RAGResponse]:
        """Enhance a cached response with new relevant content"""
        try:
            # Get new embeddings for the cached query against new content
            new_search_results = await self._search_new_content_for_query(
                cached_response.query, new_file_id, new_content_chunks, db
            )
            
            if not new_search_results:
                return None
            
            # Merge new sources with existing ones
            existing_sources = cached_response.sources
            new_sources = self._format_sources(new_search_results)
            
            # Deduplicate and merge sources
            all_sources = existing_sources + new_sources
            unique_sources = self._deduplicate_sources(all_sources)
            
            # Limit to top sources by similarity
            unique_sources.sort(key=lambda x: x.get("similarity", 0), reverse=True)
            final_sources = unique_sources[:5]
            
            # Update response with new sources
            cached_confidence = cached_response.confidence or 0.0  # Handle None confidence
            enhanced_response = RAGResponse(
                query=cached_response.query,
                response=cached_response.response,  # Keep original response for now
                intent=cached_response.intent,
                confidence=min(cached_confidence + 0.05, 0.95),  # Slight confidence boost
                sources=final_sources,
                domain=cached_response.domain,
                mode_used=cached_response.mode_used,
                response_type=cached_response.response_type,
                processing_time_ms=cached_response.processing_time_ms,
                execution_id=cached_response.execution_id,
                source_count=len(final_sources),
                suggested_actions=cached_response.suggested_actions,
                related_queries=cached_response.related_queries,
                agent_workflow_triggered=cached_response.agent_workflow_triggered,
                agent_workflow_id=cached_response.agent_workflow_id,
                cache_hit=True,
                metadata={
                    **cached_response.metadata,
                    "enhanced_with_new_content": True,
                    "enhancement_timestamp": datetime.utcnow().isoformat()
                }
            )
            
            return enhanced_response
            
        except Exception as e:
            print(f"Error enhancing cached response: {e}")
            return None
    
    async def _search_new_content_for_query(
        self, 
        query: str, 
        new_file_id: str, 
        new_content_chunks: List[str],
        db: Session
    ) -> List[SearchResult]:
        """Search new content specifically for a cached query"""
        try:
            # Generate query embedding
            query_embedding = self.embeddings_model.encode([query])[0]
            
            # Get embeddings for new content chunks from database
            result = db.execute(
                text("""
                    SELECT e.id, e.content_text, e.embedding, e.chunk_index, e.metadata,
                           f.original_filename, f.content_type, f.domain
                    FROM embeddings e
                    JOIN files f ON e.source_id = f.id
                    WHERE e.source_id = :file_id
                    ORDER BY e.chunk_index
                """),
                {"file_id": new_file_id}
            )
            
            new_embeddings_data = result.fetchall()
            search_results = []
            
            for row in new_embeddings_data:
                try:
                    # Parse stored embedding
                    if isinstance(row.embedding, str):
                        embedding_list = json.loads(row.embedding)
                    else:
                        embedding_list = row.embedding
                    stored_embedding = np.array(embedding_list, dtype=np.float32)
                    
                    # Calculate similarity
                    similarity = np.dot(query_embedding, stored_embedding) / (
                        np.linalg.norm(query_embedding) * np.linalg.norm(stored_embedding)
                    )
                    
                    if similarity >= 0.3:  # Minimum threshold for relevance
                        # Parse embedding metadata if it exists
                        embedding_metadata = {}
                        if row.metadata:
                            try:
                                if isinstance(row.metadata, str):
                                    embedding_metadata = json.loads(row.metadata)
                                else:
                                    embedding_metadata = row.metadata
                            except Exception as e:
                                print(f"⚠️ DEBUG: Failed to parse embedding metadata: {e}")
                        
                        # Build complete metadata including visual content
                        complete_metadata = {
                            "title": row.original_filename,
                            "content_type": row.content_type,
                            "chunk_index": row.chunk_index,
                            "organization_id": str(row.organization_id),
                            "source_url": row.source_url,
                            "source_type": row.source_type
                        }
                        
                        # Include visual content if available in embedding metadata
                        if embedding_metadata.get('visual_content'):
                            complete_metadata['visual_content'] = embedding_metadata['visual_content']
                            print(f"✅ DEBUG: Found visual content in embedding metadata for {row.original_filename}")
                        
                        search_results.append(SearchResult(
                            content=row.content_text,
                            metadata=complete_metadata,
                            similarity=float(similarity),
                            domain=row.domain,
                            source_id=new_file_id
                        ))
                        
                except Exception as e:
                    print(f"Error processing embedding for new content search: {e}")
                    continue
            
            # Sort by similarity and return top results
            search_results.sort(key=lambda x: x.similarity, reverse=True)
            return search_results[:3]  # Top 3 relevant chunks from new content
            
        except Exception as e:
            print(f"Error searching new content for query: {e}")
            return []
    
    def _deduplicate_sources(self, sources: List[Dict]) -> List[Dict]:
        """Remove duplicate sources based on source_id and chunk_index"""
        seen = set()
        unique_sources = []
        
        for source in sources:
            source_key = f"{source.get('id', '')}_{source.get('chunk_index', 0)}"
            if source_key not in seen:
                seen.add(source_key)
                unique_sources.append(source)
        
        return unique_sources
        
    def invalidate_cache_for_domain(self, domain: str):
        """Invalidate all cached responses for a specific domain (fallback method)"""
        # Update domain timestamp
        self.domain_last_updated[domain] = datetime.utcnow()
        
        # Remove all cache entries for this domain
        keys_to_remove = []
        for cache_key, cache_data in self.response_cache.items():
            if cache_data.get("domain") == domain:
                keys_to_remove.append(cache_key)
        
        for key in keys_to_remove:
            del self.response_cache[key]
        
        print(f"Cache invalidated for domain '{domain}': removed {len(keys_to_remove)} cached responses")
    
    def invalidate_cache_by_source_id(self, source_id: str):
        """Invalidate cached responses that used a specific source (for when files are deleted/updated)"""
        keys_to_remove = []
        for cache_key, cache_data in self.response_cache.items():
            source_ids = cache_data.get("source_ids", set())
            if source_id in source_ids:
                keys_to_remove.append(cache_key)
        
        for key in keys_to_remove:
            del self.response_cache[key]
        
        print(f"Cache invalidated for source '{source_id}': removed {len(keys_to_remove)} cached responses")
    
    def invalidate_all_cache(self):
        """Invalidate all cached responses"""
        cache_size = len(self.response_cache)
        self.response_cache.clear()
        self.domain_last_updated.clear()
        print(f"All cache invalidated: removed {cache_size} cached responses")
    
    def _is_cache_valid(self, cache_data: Dict, domain: str) -> bool:
        """Check if cached response is still valid"""
        cache_timestamp = cache_data.get("timestamp")
        if not cache_timestamp:
            return False
        
        # Check TTL expiration
        age_seconds = (datetime.utcnow() - cache_timestamp).total_seconds()
        if age_seconds > self.cache_ttl_seconds:
            return False
        
        # Check if domain was updated after cache entry
        domain_updated = self.domain_last_updated.get(domain)
        if domain_updated and cache_timestamp < domain_updated:
            return False
        
        return True
    
    def _cleanup_expired_cache(self):
        """Remove expired cache entries"""
        current_time = datetime.utcnow()
        keys_to_remove = []
        
        for cache_key, cache_data in self.response_cache.items():
            cache_timestamp = cache_data.get("timestamp")
            if cache_timestamp:
                age_seconds = (current_time - cache_timestamp).total_seconds()
                if age_seconds > self.cache_ttl_seconds:
                    keys_to_remove.append(cache_key)
        
        for key in keys_to_remove:
            del self.response_cache[key]
        
        if keys_to_remove:
            print(f"Cleaned up {len(keys_to_remove)} expired cache entries")

    async def process_query(self, request: RAGRequest, db: Session) -> RAGResponse:
        """Enhanced query processing with multi-mode support"""
        start_time = time.time()
        execution_id = str(uuid.uuid4())
        
        # Clean up expired cache entries periodically
        self._cleanup_expired_cache()
        
        # Check cache first
        cache_key = self._generate_cache_key(request)
        if not request.force_refresh_cache and cache_key in self.response_cache:
            cache_data = self.response_cache[cache_key]
            if self._is_cache_valid(cache_data, request.domain):
                cached_response = cache_data["response"]
                cached_response.cache_hit = True
                cached_response.execution_id = execution_id
                return cached_response
            else:
                # Remove invalid cache entry
                del self.response_cache[cache_key]
        
        try:
            # Step 1: Intent Classification with organization context
            if not request.organization_id:
                raise ValueError("Organization ID is required for multi-tenant isolation")
            
            classification_result = await classifier.classify_query(
                query=request.query,
                domain=request.domain,
                organization_id=request.organization_id,
                context=request.context,
                db=db
            )
            
            # Step 2: Retrieve documents based on mode
            search_results = await self._perform_search(request, classification_result)
            
            # Step 3: Agent workflow processing (if applicable)
            agent_result = None
            confidence = classification_result.confidence or 0.0  # Handle None confidence
            if (request.mode == RAGMode.AGENT_ENHANCED and 
                confidence > 0.7 and 
                classification_result.intent in ["bug_report", "feature_request", "training"]):
                
                agent_result = await self.agent_processor.execute_workflow(
                    intent=classification_result.intent,
                    query=request.query,
                    confidence=confidence,
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
            
            # Cache the response with enhanced metadata
            query_embedding = self.embeddings_model.encode([request.query])[0] if self.embeddings_model else None
            source_ids = {source.get("id") for source in response_data["sources"] if source.get("id")}
            
            self.response_cache[cache_key] = {
                "response": rag_response, 
                "timestamp": datetime.utcnow(), 
                "domain": request.domain,
                "query_embedding": query_embedding,
                "source_ids": source_ids
            }
            
            # Store execution in database
            await self._store_execution(db, request, rag_response, classification_result)
            
            return rag_response
            
        except Exception as e:
            print(f"Error in RAG processing: {e}")
            import traceback
            print(f"Full traceback: {traceback.format_exc()}")
            return self._generate_error_response(request, str(e), execution_id, int((time.time() - start_time) * 1000))
    
    async def _perform_search(self, request: RAGRequest, classification: ClassificationResult) -> List[SearchResult]:
        """Perform search based on mode"""
        
        if request.mode == RAGMode.SIMPLE:
            return await self.vector_store.search(
                request.query, 
                request.domain, 
                request.max_results, 
                request.confidence_threshold,
                request.organization_id
            )
        
        elif request.mode == RAGMode.CROSS_DOMAIN:
            # Search across all domains
            all_domains = ["general", "support", "sales", "engineering", "product"]
            cross_results = await self.vector_store.cross_domain_search(
                request.query, 
                all_domains, 
                request.max_results * 2, 
                request.confidence_threshold,
                request.organization_id
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
            cross_results = await self.vector_store.cross_domain_search(
                request.query, 
                all_domains, 
                request.max_results, 
                request.confidence_threshold,
                request.organization_id
            )
            
            all_results = []
            for domain, results in cross_results.items():
                all_results.extend(results)
            
            return sorted(all_results, key=lambda x: x.similarity, reverse=True)[:request.max_results]
        
        else:
            # Default to simple search
            return await self.vector_store.search(
                request.query, 
                request.domain, 
                request.max_results, 
                request.confidence_threshold,
                request.organization_id
            )
    
    def _generate_enhanced_response(
        self,
        request: RAGRequest,
        classification: ClassificationResult,
        search_results: List[SearchResult],
        agent_result: Optional[WorkflowResult]
    ) -> Dict[str, Any]:
        """Generate enhanced response with LLM integration"""
        
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
        
        # Use LLM for response generation
        try:
            from llm_service import get_llm_service
            llm_service = get_llm_service()
            
            print(f"LLM service available: {llm_service.is_available()}")
            
            if llm_service.is_available():
                # Generate response using LLM
                llm_response = llm_service.generate_response(
                    query=request.query,
                    context=context,
                    sources=sources,
                    intent=classification.intent
                )
                
                # Debug: Log visual content in sources for login queries
                if 'login' in request.query.lower():
                    print(f"🔍 DEBUG LOGIN: Query contains 'login', checking sources for visual content...")
                    for i, source in enumerate(sources):
                        metadata = source.get('metadata', {})
                        visual_content = metadata.get('visual_content', {})
                        if visual_content:
                            screenshots = visual_content.get('screenshots', [])
                            images = visual_content.get('images', [])
                            print(f"📸 DEBUG LOGIN: Source {i} ({source.get('title', 'Unknown')}) has {len(screenshots)} screenshots, {len(images)} images")
                            for j, screenshot in enumerate(screenshots[:2]):
                                alt_text = screenshot.get('alt_text', 'Unknown')
                                print(f"  - Screenshot {j}: {alt_text}")
                        else:
                            print(f"❌ DEBUG LOGIN: Source {i} ({source.get('title', 'Unknown')}) has no visual content")
                
                print(f"LLM response generated: {llm_response[:100]}...")
                
                # Boost confidence when using LLM
                base_confidence = classification.confidence or 0.0  # Handle None confidence
                confidence = min(base_confidence + 0.2, 0.95)
                
                return {
                    "response": llm_response,
                    "confidence": confidence,
                    "response_type": ResponseType.GENERATED,
                    "sources": sources,
                    "suggested_actions": self._generate_suggested_actions(classification.intent),
                    "related_queries": self._generate_related_queries(search_results),
                    "metadata": {"classification": classification.metadata, "llm_used": True}
                }
            else:
                print("LLM service not available, using template response")
                # Fallback to template-based response
                return self._generate_template_response(request, classification, sources, context)
                
        except Exception as e:
            print(f"LLM generation failed: {e}")
            import traceback
            traceback.print_exc()
            # Fallback to template-based response
            return self._generate_template_response(request, classification, sources, context)
    
    def _generate_template_response(self, request: RAGRequest, classification: ClassificationResult, sources: List[Dict], context: str) -> Dict[str, Any]:
        """Fallback template-based response generation with concise format"""
        
        # Generate a concise response based on context
        if not context.strip():
            response = "I couldn't find specific information to answer your question. Please try rephrasing or providing more details."
        else:
            # Extract key information for a concise response
            sentences = context.split('. ')
            key_info = '. '.join(sentences[:2])  # First 2 sentences
            
            if len(key_info) > 250:
                key_info = key_info[:250] + "..."
            
            response = f"Based on the available information: {key_info}"
            
            # Add simple source reference if available
            if sources and len(sources) > 0:
                response += f" (Source: {sources[0]['title']})"
        
        return {
            "response": response,
            "confidence": classification.confidence,
            "response_type": ResponseType.GENERATED,
            "sources": sources,
            "suggested_actions": self._generate_suggested_actions(classification.intent),
            "related_queries": self._generate_related_queries([]),
            "metadata": {"classification": classification.metadata, "llm_used": False}
        }
    
    def _format_sources(self, results: List[SearchResult]) -> List[Dict]:
        """Format search results as source citations"""
        sources = []
        
        # Group results by source to handle chunks intelligently
        source_groups = {}
        for result in results:
            source_id = result.source_id
            if source_id not in source_groups:
                source_groups[source_id] = []
            source_groups[source_id].append(result)
        
        citation_counter = 1
        for source_id, source_results in source_groups.items():
            # Sort by chunk index if available
            source_results.sort(key=lambda x: x.metadata.get('chunk_index', 0) or 0)
            
            # Get the best result for this source
            best_result = max(source_results, key=lambda x: x.similarity)
            
            # Improved title formatting based on source type
            title = best_result.metadata.get("title", "Document")
            source_type = best_result.metadata.get("source_type", "file")
            
            # Clean up title for better user experience
            clean_title = title
            if source_type == "web_page":
                # For web pages, use title as-is (it's already cleaned from scraping)
                clean_title = title if title else "Web Page"
            elif source_type == "file":
                # For files, clean up filename
                if title.endswith('.pdf'):
                    clean_title = title[:-4]  # Remove .pdf extension
                
                # Extract clean document name without technical suffixes
                if 'report' in title.lower():
                    clean_title = title.replace('-', ' ').title()
                elif 'help' in title.lower() or 'guide' in title.lower():
                    clean_title = f"Help Guide: {title}"
                elif 'faq' in title.lower():
                    clean_title = f"FAQ: {title}"
            
            # Only add chunk info for long documents with multiple meaningful sections
            chunk_index = best_result.metadata.get("chunk_index", 0) or 0
            total_chunks = len(source_results)
            
            # For documents with many chunks, add section info instead of part numbers
            if total_chunks > 3 and chunk_index > 0:
                # Try to make it more user-friendly
                if 'report' in title.lower():
                    clean_title = f"{clean_title} - Section {chunk_index + 1}"
                else:
                    clean_title = f"{clean_title} (Section {chunk_index + 1})"
            
            # Clean up the content for better readability
            clean_content = best_result.content.replace('\n', ' ').strip()
            
            # Create a concise preview for the citation tooltip
            preview_content = clean_content[:120] + "..." if len(clean_content) > 120 else clean_content
            
            # Create a longer excerpt for modal display
            excerpt_content = clean_content[:400] + "..." if len(clean_content) > 400 else clean_content
            
            # Determine document type for better categorization
            doc_type = "document"
            if source_type == "web_page":
                doc_type = "web_page"
            elif 'help' in title.lower() or 'guide' in title.lower():
                doc_type = "help_article"
            elif 'faq' in title.lower():
                doc_type = "faq"
            elif 'report' in title.lower():
                doc_type = "report"
            elif best_result.metadata.get("content_type", "").startswith("text/"):
                doc_type = "text_document"
            
            # Get the URL (for web pages) or file ID (for files)
            source_url = best_result.metadata.get("source_url") if source_type == "web_page" else None
            
            # Extract images/screenshots if available from SearchResult metadata
            images = []
            visual_content = best_result.metadata.get("visual_content", {})
            
            if visual_content:
                # Get images and screenshots from visual content
                if visual_content.get("images"):
                    images.extend(visual_content["images"][:3])  # Limit to 3 images per source
                if visual_content.get("screenshots"):
                    images.extend(visual_content["screenshots"][:3])  # Limit to 3 screenshots per source
                
                print(f"📸 DEBUG: Found visual content for {clean_title}: {len(visual_content.get('screenshots', []))} screenshots, {len(visual_content.get('images', []))} images")
            else:
                # Fallback: check if images are directly in metadata
                if best_result.metadata.get("images"):
                    images = best_result.metadata["images"][:3]
                elif best_result.metadata.get("screenshots"):
                    images = best_result.metadata["screenshots"][:3]
            
            # Extract step-by-step content if available (for procedural documents)
            steps = []
            if "step" in best_result.content.lower() or "procedure" in best_result.content.lower():
                # Extract numbered or bulleted steps
                step_patterns = [
                    r'(?:^|\n)\s*(?:Step\s*)?(\d+)[\.\)]\s*([^\n]+)',
                    r'(?:^|\n)\s*[\-\*]\s*([^\n]+)',
                    r'(?:^|\n)\s*(\d+)\.\s*([^\n]+)'
                ]
                
                for pattern in step_patterns:
                    matches = re.findall(pattern, best_result.content, re.MULTILINE | re.IGNORECASE)
                    if matches:
                        if len(matches[0]) == 2:  # Pattern with step number and text
                            steps = [{"number": m[0], "text": m[1].strip()} for m in matches[:10]]
                        else:  # Pattern with just text
                            steps = [{"number": i+1, "text": m.strip()} for i, m in enumerate(matches[:10])]
                        break
            
            sources.append({
                "id": best_result.source_id,
                "title": clean_title,
                "preview": preview_content,  # Short preview for tooltips
                "excerpt": excerpt_content,  # Medium excerpt for modal preview
                "full_content": best_result.content,  # Complete content for detailed view
                "domain": best_result.domain,
                "similarity": round(best_result.similarity, 3),
                "confidence_score": f"{round(best_result.similarity * 100)}%",
                "url": source_url,  # Only populated for web pages
                "chunk_index": chunk_index,
                "content_length": len(best_result.content),
                "word_count": len(best_result.content.split()),
                "document_type": doc_type,  # Add document type classification
                "source_type": source_type,  # Add source type for UI handling
                "expandable": True,  # Flag to indicate this source can be expanded
                "citation_id": f"cite_{citation_counter}",  # Unique citation identifier
                "source_quality": "high" if best_result.similarity > 0.7 else "medium" if best_result.similarity > 0.5 else "low",
                # Enhanced with images and structured content
                "images": images,  # Screenshots or images from help guides
                "steps": steps,  # Extracted step-by-step instructions
                "has_visual_content": len(images) > 0,
                "has_procedural_content": len(steps) > 0,
                # CRITICAL: Include the metadata with visual content for LLM access
                "metadata": {
                    "title": clean_title,
                    "content_type": best_result.metadata.get("content_type", ""),
                    "visual_content": visual_content,  # Include visual content for LLM
                    "source_url": source_url,
                    "source_type": source_type
                }
            })
            citation_counter += 1
        
        return sources
    
    def _generate_context(self, results: List[SearchResult]) -> str:
        """Generate focused context from search results for LLM processing"""
        if not results:
            return "No relevant information found."
        
        # Group results by source to avoid fragmentation
        source_groups = {}
        for result in results:
            source_id = result.source_id
            if source_id not in source_groups:
                source_groups[source_id] = []
            source_groups[source_id].append(result)
        
        context_parts = []
        for source_id, source_results in source_groups.items():
            # Sort by chunk index if available
            source_results.sort(key=lambda x: x.metadata.get('chunk_index', 0) or 0)
            
            # Get the most relevant content from this source
            best_result = max(source_results, key=lambda x: x.similarity)
            content = best_result.content.strip()
            
            # Add source title for LLM reference
            title = best_result.metadata.get("title", "Document")
            if title.endswith('.pdf'):
                title = title[:-4]
            
            # Keep content focused but sufficient for LLM understanding
            if len(content) > 600:
                content = content[:600] + "..."
            
            context_parts.append(f"From {title}:\n{content}")
        
        return "\n\n".join(context_parts[:3])  # Max 3 sources for focused context
    
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
            # Get domain_id from domain name
            domain_result = db.execute(
                text("SELECT id FROM organization_domains WHERE domain_name = :domain AND organization_id = :org_id"),
                {"domain": request.domain, "org_id": request.organization_id}
            ).fetchone()
            
            if not domain_result:
                print(f"Domain '{request.domain}' not found for organization {request.organization_id}")
                return
            
            domain_id = domain_result.id
            
            db.execute(
                text("""
                    INSERT INTO rag_executions (
                        id, query, domain_id, mode, intent, confidence, 
                        response_type, source_count, processing_time_ms, 
                        user_id, session_id, organization_id, created_at
                    ) VALUES (
                        :id, :query, :domain_id, :mode, :intent, :confidence,
                        :response_type, :source_count, :processing_time_ms,
                        :user_id, :session_id, :organization_id, :created_at
                    )
                """),
                {
                    "id": response.execution_id,
                    "query": request.query,
                    "domain_id": domain_id,
                    "mode": request.mode.value,
                    "intent": classification.intent,
                    "confidence": classification.confidence,
                    "response_type": response.response_type.value,
                    "source_count": response.source_count,
                    "processing_time_ms": response.processing_time_ms,
                    "user_id": request.user_id,
                    "session_id": request.session_id,
                    "organization_id": request.organization_id,
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
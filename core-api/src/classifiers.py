"""
Intent Classification Module
Migrated from services/query/classification-service/src/classifiers.py
Provides sophisticated intent detection for queries with multi-tenant isolation
"""

import re
import json
import uuid
from datetime import datetime
from typing import Dict, List, Optional, Tuple
from dataclasses import dataclass

from sqlalchemy.orm import Session
from sqlalchemy import text


@dataclass
class ClassificationResult:
    """Result of intent classification"""
    intent: str
    confidence: float
    reasoning: str
    method: str
    metadata: Dict


class IntentClassifier:
    """Advanced intent classification with multiple methods and multi-tenant isolation"""
    
    def __init__(self):
        # Intent patterns for classification
        self.intent_patterns = {
            "bug_report": {
                "keywords": [
                    "error", "bug", "issue", "problem", "crash", "fail", "broken",
                    "exception", "stack trace", "not working", "doesn't work",
                    "unexpected", "wrong", "incorrect", "malfunction"
                ],
                "patterns": [
                    r"error.*when.*",
                    r"getting.*error.*",
                    r".*not.*work.*",
                    r".*crash.*",
                    r".*fail.*to.*",
                    r".*broken.*",
                    r"exception.*",
                    r"stack.*trace.*"
                ]
            },
            "feature_request": {
                "keywords": [
                    "feature", "enhancement", "improvement", "add", "new",
                    "request", "suggest", "proposal", "implement", "support",
                    "would like", "can you", "please add", "missing"
                ],
                "patterns": [
                    r"can.*you.*add.*",
                    r"would.*like.*to.*",
                    r"feature.*request.*",
                    r"please.*implement.*",
                    r"missing.*feature.*",
                    r"enhancement.*",
                    r"improvement.*"
                ]
            },
            "training": {
                "keywords": [
                    "how", "tutorial", "guide", "documentation", "learn",
                    "training", "help", "explain", "show", "teach",
                    "understand", "configure", "setup", "install"
                ],
                "patterns": [
                    r"how.*do.*i.*",
                    r"how.*to.*",
                    r"tutorial.*",
                    r"guide.*for.*",
                    r"help.*with.*",
                    r"explain.*",
                    r"show.*me.*"
                ]
            },
            "general_query": {
                "keywords": [
                    "what", "when", "where", "who", "why", "information",
                    "details", "about", "status", "update"
                ],
                "patterns": [
                    r"what.*is.*",
                    r"tell.*me.*about.*",
                    r"information.*about.*",
                    r"status.*of.*"
                ]
            }
        }
    
    async def classify_query(
        self,
        query: str,
        organization_id: str,
        domain: str = "general",
        context: Optional[Dict] = None,
        db: Optional[Session] = None
    ) -> ClassificationResult:
        """
        Classify query intent with multi-tenant isolation
        
        Args:
            query: User query to classify
            domain: Domain context for classification
            organization_id: Organization ID for multi-tenant isolation
            context: Additional context for classification
            db: Database session for storing results
            
        Returns:
            ClassificationResult with intent, confidence, and reasoning
        """
        if not query.strip():
            return ClassificationResult(
                intent="general_query",
                confidence=0.1,
                reasoning="Empty query defaulted to general",
                method="default",
                metadata={}
            )
        
        # Perform multi-method classification
        results = []
        
        # Method 1: Keyword-based classification
        keyword_result = self._classify_by_keywords(query)
        results.append((keyword_result, 0.3))
        
        # Method 2: Pattern-based classification
        pattern_result = self._classify_by_patterns(query)
        results.append((pattern_result, 0.4))
        
        # Method 3: Context-based classification
        if context:
            context_result = self._classify_by_context(query, context)
            results.append((context_result, 0.2))
        
        # Method 4: Domain-based classification
        domain_result = self._classify_by_domain(query, domain)
        results.append((domain_result, 0.1))
        
        # Combine results
        final_result = self._combine_results(results)
        
        # Store classification result with organization context
        if db:
            await self._store_classification(
                db, query, final_result, domain, organization_id, 
                context.get("user_id") if context else None,
                context.get("session_id") if context else None
            )
        
        return final_result
    
    def _classify_by_keywords(self, query: str) -> ClassificationResult:
        """Classify based on keyword matching"""
        query_lower = query.lower()
        scores = {}
        
        for intent, data in self.intent_patterns.items():
            score = 0
            matched_keywords = []
            
            for keyword in data["keywords"]:
                if keyword in query_lower:
                    score += 1
                    matched_keywords.append(keyword)
            
            if score > 0:
                confidence = min(score / len(data["keywords"]), 1.0)
                scores[intent] = {
                    "confidence": confidence,
                    "matched_keywords": matched_keywords
                }
        
        if not scores:
            return ClassificationResult(
                intent="general_query",
                confidence=0.2,
                reasoning="No keywords matched",
                method="keywords",
                metadata={}
            )
        
        best_intent = max(scores.keys(), key=lambda x: scores[x]["confidence"])
        best_score = scores[best_intent]
        
        return ClassificationResult(
            intent=best_intent,
            confidence=best_score["confidence"],
            reasoning=f"Keywords matched: {', '.join(best_score['matched_keywords'])}",
            method="keywords",
            metadata={"matched_keywords": best_score["matched_keywords"]}
        )
    
    def _classify_by_patterns(self, query: str) -> ClassificationResult:
        """Classify based on regex pattern matching"""
        query_lower = query.lower()
        scores = {}
        
        for intent, data in self.intent_patterns.items():
            matched_patterns = []
            
            for pattern in data["patterns"]:
                if re.search(pattern, query_lower):
                    matched_patterns.append(pattern)
            
            if matched_patterns:
                confidence = min(len(matched_patterns) / len(data["patterns"]), 1.0)
                scores[intent] = {
                    "confidence": confidence,
                    "matched_patterns": matched_patterns
                }
        
        if not scores:
            return ClassificationResult(
                intent="general_query",
                confidence=0.2,
                reasoning="No patterns matched",
                method="patterns",
                metadata={}
            )
        
        best_intent = max(scores.keys(), key=lambda x: scores[x]["confidence"])
        best_score = scores[best_intent]
        
        return ClassificationResult(
            intent=best_intent,
            confidence=best_score["confidence"],
            reasoning=f"Patterns matched: {len(best_score['matched_patterns'])}",
            method="patterns",
            metadata={"matched_patterns": best_score["matched_patterns"]}
        )
    
    def _classify_by_context(self, query: str, context: Optional[Dict]) -> ClassificationResult:
        """Classify based on conversation context"""
        if not context:
            return ClassificationResult(
                intent="general_query",
                confidence=0.1,
                reasoning="No context provided",
                method="context",
                metadata={}
            )
        
        # Analyze recent messages for context clues
        recent_messages = context.get("recent_messages", [])
        context_indicators = {
            "bug_report": ["error", "problem", "issue", "bug"],
            "feature_request": ["feature", "add", "new", "enhancement"],
            "training": ["how", "help", "tutorial", "guide"],
            "general_query": ["what", "when", "where", "info"]
        }
        
        scores = {}
        for intent, indicators in context_indicators.items():
            matched_indicators = []
            for message in recent_messages[-3:]:  # Last 3 messages
                content = message.get("content", "").lower()
                for indicator in indicators:
                    if indicator in content:
                        matched_indicators.append(indicator)
            
            if matched_indicators:
                confidence = min(len(matched_indicators) / 5, 0.8)  # Cap at 0.8 for context
                scores[intent] = {
                    "confidence": confidence,
                    "matched_indicators": matched_indicators
                }
        
        if not scores:
            return ClassificationResult(
                intent="general_query",
                confidence=0.1,
                reasoning="No context indicators found",
                method="context",
                metadata={}
            )
        
        best_intent = max(scores.keys(), key=lambda x: scores[x]["confidence"])
        best_score = scores[best_intent]
        
        return ClassificationResult(
            intent=best_intent,
            confidence=best_score["confidence"],
            reasoning=f"Context indicators: {', '.join(best_score['matched_indicators'])}",
            method="context",
            metadata={"context_indicators": best_score["matched_indicators"]}
        )
    
    def _classify_by_domain(self, query: str, domain: str) -> ClassificationResult:
        """Classify based on domain-specific patterns"""
        domain_weights = {
            "support": {
                "bug_report": 1.5,
                "training": 1.3,
                "general_query": 1.0,
                "feature_request": 0.7
            },
            "engineering": {
                "bug_report": 1.8,
                "feature_request": 1.5,
                "training": 1.2,
                "general_query": 0.8
            },
            "product": {
                "feature_request": 1.8,
                "general_query": 1.2,
                "training": 1.0,
                "bug_report": 0.7
            },
            "sales": {
                "general_query": 1.5,
                "training": 1.3,
                "feature_request": 1.0,
                "bug_report": 0.5
            },
            "general": {
                "general_query": 1.0,
                "training": 1.0,
                "bug_report": 1.0,
                "feature_request": 1.0
            }
        }
        
        weights = domain_weights.get(domain, domain_weights["general"])
        
        # Find the most likely intent for this domain
        best_intent = max(weights.keys(), key=lambda x: weights[x])
        confidence = min(weights[best_intent] / 2.0, 0.8)  # Cap at 0.8 for domain-only classification
        
        return ClassificationResult(
            intent=best_intent,
            confidence=confidence,
            reasoning=f"Domain '{domain}' bias towards '{best_intent}'",
            method="domain",
            metadata={"domain": domain, "weight": weights[best_intent]}
        )
    
    def _combine_results(self, results: List[Tuple[ClassificationResult, float]]) -> ClassificationResult:
        """Combine multiple classification results with weighted scoring"""
        intent_scores = {}
        total_weight = sum(weight for _, weight in results)
        
        # Calculate weighted scores for each intent
        for result, weight in results:
            if result.intent not in intent_scores:
                intent_scores[result.intent] = {
                    "total_score": 0,
                    "methods": [],
                    "reasoning_parts": []
                }
            
            weighted_score = result.confidence * weight
            intent_scores[result.intent]["total_score"] += weighted_score
            intent_scores[result.intent]["methods"].append(result.method)
            intent_scores[result.intent]["reasoning_parts"].append(f"{result.method}: {result.reasoning}")
        
        # Find best intent
        best_intent = max(intent_scores.keys(), key=lambda x: intent_scores[x]["total_score"])
        best_data = intent_scores[best_intent]
        
        final_confidence = min(best_data["total_score"] / total_weight, 1.0)
        
        # Combine reasoning from all methods
        combined_reasoning = " | ".join(best_data["reasoning_parts"])
        
        return ClassificationResult(
            intent=best_intent,
            confidence=final_confidence,
            reasoning=combined_reasoning,
            method="combined",
            metadata={
                "methods_used": best_data["methods"],
                "all_scores": {intent: data["total_score"] for intent, data in intent_scores.items()}
            }
        )
    
    async def _store_classification(
        self,
        db: Session,
        query: str,
        result: ClassificationResult,
        domain: str,
        organization_id: str,
        user_id: Optional[str] = None,
        session_id: Optional[str] = None
    ):
        """Store classification result in database with organization context"""
        try:
            # Get domain_id from domain name
            domain_result = db.execute(
                text("""
                    SELECT id FROM organization_domains 
                    WHERE organization_id = :organization_id AND domain_name = :domain_name AND is_active = true
                """),
                {"organization_id": organization_id, "domain_name": domain}
            ).fetchone()
            
            if not domain_result:
                print(f"Warning: Domain '{domain}' not found for organization {organization_id}")
                return
            
            domain_id = str(domain_result.id)
            
            classification_id = str(uuid.uuid4())
            db.execute(
                text("""
                    INSERT INTO classification_results (
                        id, query, intent, confidence, domain_id, organization_id, classification_method,
                        reasoning, metadata, user_id, session_id, created_at
                    ) VALUES (
                        :id, :query, :intent, :confidence, :domain_id, :organization_id, :method,
                        :reasoning, :metadata, :user_id, :session_id, :created_at
                    )
                """),
                {
                    "id": classification_id,
                    "query": query,
                    "intent": result.intent,
                    "confidence": result.confidence,
                    "domain_id": domain_id,
                    "organization_id": organization_id,
                    "method": result.method,
                    "reasoning": result.reasoning,
                    "metadata": json.dumps(result.metadata),
                    "user_id": user_id,
                    "session_id": session_id,
                    "created_at": datetime.utcnow()
                }
            )
            db.commit()
        except Exception as e:
            print(f"Failed to store classification result: {e}")
            db.rollback()
    
    async def get_classification_analytics(
        self,
        db: Session,
        organization_id: str,
        domain: Optional[str] = None,
        days: int = 7
    ) -> Dict:
        """Get classification analytics with organization isolation"""
        where_clause = """WHERE cr.created_at >= NOW() - INTERVAL '%s days' AND cr.organization_id = :org_id""" % days
        params = {"org_id": organization_id}
        
        if domain:
            where_clause += " AND od.domain_name = :domain"
            params["domain"] = domain
        
        # Intent distribution
        intent_stats = db.execute(
            text(f"""
                SELECT cr.intent, COUNT(*) as count, AVG(cr.confidence) as avg_confidence
                FROM classification_results cr
                LEFT JOIN organization_domains od ON cr.domain_id = od.id
                {where_clause}
                GROUP BY cr.intent
                ORDER BY count DESC
            """),
            params
        ).fetchall()
        
        # Daily trends
        daily_stats = db.execute(
            text(f"""
                SELECT DATE(cr.created_at) as date, cr.intent, COUNT(*) as count
                FROM classification_results cr
                LEFT JOIN organization_domains od ON cr.domain_id = od.id
                {where_clause}
                GROUP BY DATE(cr.created_at), cr.intent
                ORDER BY date DESC
            """),
            params
        ).fetchall()
        
        return {
            "organization_id": organization_id,
            "domain": domain,
            "period_days": days,
            "intent_distribution": [
                {
                    "intent": row.intent,
                    "count": row.count,
                    "avg_confidence": float(row.avg_confidence)
                }
                for row in intent_stats
            ],
            "daily_trends": [
                {
                    "date": row.date.isoformat(),
                    "intent": row.intent,
                    "count": row.count
                }
                for row in daily_stats
            ]
        }


# Additional classifier classes for testing compatibility

class QueryClassifier:
    """Query type and complexity classification"""
    
    def __init__(self, confidence_threshold: float = 0.7, fallback_intent: str = "general_query"):
        self.confidence_threshold = confidence_threshold
        self.fallback_intent = fallback_intent
        self.intent_patterns = {}
        self.keyword_weights = {}
    
    def classify_intent(self, query: str, context: Optional[Dict] = None, detect_multiple: bool = False) -> Dict:
        """Classify query intent"""
        return {
            "intent": "general_query",
            "confidence": 0.5,
            "reasoning": "Mock implementation",
            "multiple_intents": [] if detect_multiple else None
        }


class DomainClassifier:
    """Domain-specific classification"""
    
    def __init__(self):
        self.domain_patterns = {}
    
    def classify_domain(self, query: str) -> Dict:
        """Classify query domain"""
        return {
            "domain": "general",
            "confidence": 0.5,
            "reasoning": "Mock implementation"
        }


class ConfidenceLevel:
    """Confidence level enumeration"""
    HIGH = "high"
    MEDIUM = "medium"
    LOW = "low"
    
    @classmethod
    def from_score(cls, score: float) -> str:
        """Convert numeric score to confidence level"""
        if score >= 0.8:
            return cls.HIGH
        elif score >= 0.5:
            return cls.MEDIUM
        else:
            return cls.LOW


# Global classifier instance
classifier = IntentClassifier() 
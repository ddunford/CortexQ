"""
Intent Classification Module
Migrated from services/query/classification-service/src/classifiers.py
Provides sophisticated intent detection for queries
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
    """Advanced intent classification with multiple methods"""
    
    def __init__(self):
        self.intent_patterns = {
            "bug_report": {
                "keywords": ["error", "bug", "crash", "broken", "issue", "problem", "not working", "fail", "exception"],
                "patterns": [
                    r".*error.*",
                    r".*crash.*",
                    r".*not working.*",
                    r".*broken.*",
                    r".*fail(s|ed|ing)?.*",
                    r".*exception.*",
                    r".*bug.*"
                ],
                "context_indicators": ["stack trace", "error message", "exception", "debug"]
            },
            "feature_request": {
                "keywords": ["feature", "request", "add", "new", "enhancement", "improvement", "want", "need", "wish"],
                "patterns": [
                    r".*feature.*",
                    r".*request.*",
                    r"can you add.*",
                    r".*enhancement.*",
                    r"i need.*",
                    r"i want.*",
                    r"please add.*"
                ],
                "context_indicators": ["roadmap", "backlog", "feature", "enhancement"]
            },
            "training": {
                "keywords": ["how", "tutorial", "guide", "help", "documentation", "learn", "explain", "show", "teach"],
                "patterns": [
                    r"how to.*",
                    r".*tutorial.*",
                    r".*guide.*",
                    r"help me.*",
                    r"how do i.*",
                    r"can you show.*",
                    r".*documentation.*"
                ],
                "context_indicators": ["documentation", "guide", "tutorial", "help"]
            },
            "general_query": {
                "keywords": ["what", "when", "where", "who", "why", "information", "details"],
                "patterns": [
                    r"what is.*",
                    r"when does.*",
                    r"where can.*",
                    r"who is.*",
                    r"why does.*"
                ],
                "context_indicators": ["information", "details", "about"]
            }
        }
    
    async def classify_query(
        self,
        query: str,
        domain: str = "general",
        context: Optional[Dict] = None,
        db: Optional[Session] = None
    ) -> ClassificationResult:
        """Classify query intent using multiple methods"""
        
        query_lower = query.lower().strip()
        
        # Method 1: Keyword-based classification
        keyword_result = self._classify_by_keywords(query_lower)
        
        # Method 2: Pattern matching
        pattern_result = self._classify_by_patterns(query_lower)
        
        # Method 3: Context-aware classification
        context_result = self._classify_by_context(query_lower, context)
        
        # Method 4: Domain-specific classification
        domain_result = self._classify_by_domain(query_lower, domain)
        
        # Combine results with weighted scoring
        final_result = self._combine_results([
            (keyword_result, 0.3),
            (pattern_result, 0.4),
            (context_result, 0.2),
            (domain_result, 0.1)
        ])
        
        # Store classification result in database if available
        if db:
            await self._store_classification(db, query, final_result, domain)
        
        return final_result
    
    def _classify_by_keywords(self, query: str) -> ClassificationResult:
        """Classify based on keyword matching"""
        scores = {}
        
        for intent, data in self.intent_patterns.items():
            score = 0
            matched_keywords = []
            
            for keyword in data["keywords"]:
                if keyword in query:
                    score += 1
                    matched_keywords.append(keyword)
            
            if score > 0:
                confidence = min(score / len(data["keywords"]), 1.0)
                scores[intent] = {
                    "confidence": confidence,
                    "matched_keywords": matched_keywords,
                    "score": score
                }
        
        if not scores:
            return ClassificationResult(
                intent="general_query",
                confidence=0.3,
                reasoning="No specific keywords detected, defaulting to general query",
                method="keyword",
                metadata={}
            )
        
        best_intent = max(scores.keys(), key=lambda x: scores[x]["confidence"])
        best_score = scores[best_intent]
        
        return ClassificationResult(
            intent=best_intent,
            confidence=best_score["confidence"],
            reasoning=f"Matched keywords: {', '.join(best_score['matched_keywords'])}",
            method="keyword",
            metadata={"matched_keywords": best_score["matched_keywords"]}
        )
    
    def _classify_by_patterns(self, query: str) -> ClassificationResult:
        """Classify based on regex pattern matching"""
        scores = {}
        
        for intent, data in self.intent_patterns.items():
            matched_patterns = []
            
            for pattern in data["patterns"]:
                if re.search(pattern, query, re.IGNORECASE):
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
                confidence=0.3,
                reasoning="No patterns matched, defaulting to general query",
                method="pattern",
                metadata={}
            )
        
        best_intent = max(scores.keys(), key=lambda x: scores[x]["confidence"])
        best_score = scores[best_intent]
        
        return ClassificationResult(
            intent=best_intent,
            confidence=best_score["confidence"],
            reasoning=f"Matched patterns: {len(best_score['matched_patterns'])} out of {len(self.intent_patterns[best_intent]['patterns'])}",
            method="pattern",
            metadata={"matched_patterns": best_score["matched_patterns"]}
        )
    
    def _classify_by_context(self, query: str, context: Optional[Dict]) -> ClassificationResult:
        """Classify based on conversation context"""
        if not context:
            return ClassificationResult(
                intent="general_query",
                confidence=0.1,
                reasoning="No context available",
                method="context",
                metadata={}
            )
        
        # Check for context indicators in previous messages
        context_text = " ".join([
            msg.get("content", "") for msg in context.get("recent_messages", [])
        ]).lower()
        
        scores = {}
        for intent, data in self.intent_patterns.items():
            score = 0
            matched_indicators = []
            
            for indicator in data["context_indicators"]:
                if indicator in context_text:
                    score += 1
                    matched_indicators.append(indicator)
            
            if score > 0:
                confidence = min(score / len(data["context_indicators"]), 1.0)
                scores[intent] = {
                    "confidence": confidence,
                    "matched_indicators": matched_indicators
                }
        
        if not scores:
            return ClassificationResult(
                intent="general_query",
                confidence=0.2,
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
        user_id: Optional[str] = None,
        session_id: Optional[str] = None
    ):
        """Store classification result in database"""
        try:
            classification_id = str(uuid.uuid4())
            db.execute(
                text("""
                    INSERT INTO classification_results (
                        id, query, intent, confidence, domain, classification_method,
                        reasoning, metadata, user_id, session_id, created_at
                    ) VALUES (
                        :id, :query, :intent, :confidence, :domain, :method,
                        :reasoning, :metadata, :user_id, :session_id, :created_at
                    )
                """),
                {
                    "id": classification_id,
                    "query": query,
                    "intent": result.intent,
                    "confidence": result.confidence,
                    "domain": domain,
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
        domain: Optional[str] = None,
        days: int = 7
    ) -> Dict:
        """Get classification analytics"""
        where_clause = "WHERE created_at >= NOW() - INTERVAL '%s days'" % days
        if domain:
            where_clause += f" AND domain = '{domain}'"
        
        # Intent distribution
        intent_stats = db.execute(
            text(f"""
                SELECT intent, COUNT(*) as count, AVG(confidence) as avg_confidence
                FROM classification_results
                {where_clause}
                GROUP BY intent
                ORDER BY count DESC
            """)
        ).fetchall()
        
        # Daily trends
        daily_stats = db.execute(
            text(f"""
                SELECT DATE(created_at) as date, intent, COUNT(*) as count
                FROM classification_results
                {where_clause}
                GROUP BY DATE(created_at), intent
                ORDER BY date DESC
            """)
        ).fetchall()
        
        return {
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


# Global classifier instance
classifier = IntentClassifier() 
"""
Intent Classifier - Core classification logic
Combines keyword matching, pattern recognition, and LLM-based classification
"""

import re
import time
import json
import asyncio
import hashlib
from typing import Dict, Any, List, Optional, Tuple
import httpx
from openai import AsyncOpenAI
import logging

from config import Settings
from models import ClassificationResult, IntentDefinition, INTENT_DEFINITIONS, IntentCategory

logger = logging.getLogger(__name__)


class IntentClassifier:
    """Main intent classification engine"""
    
    def __init__(self, settings: Settings):
        self.settings = settings
        self.openai_client = None
        self.ollama_client = None
        self.cache = {}  # Simple in-memory cache
        
    async def initialize(self):
        """Initialize the classifier"""
        logger.info("Initializing Intent Classifier...")
        
        # Initialize OpenAI client if configured
        if (self.settings.LLM_PROVIDER == "openai" or 
            self.settings.OPENAI_API_KEY != "your_openai_key_here"):
            self.openai_client = AsyncOpenAI(api_key=self.settings.OPENAI_API_KEY)
            
        # Initialize Ollama client
        self.ollama_client = httpx.AsyncClient(timeout=self.settings.LLM_TIMEOUT)
        
        logger.info("Intent Classifier initialized successfully")
    
    async def cleanup(self):
        """Cleanup resources"""
        if self.ollama_client:
            await self.ollama_client.aclose()
    
    async def classify(
        self, 
        query: str, 
        context: Optional[Dict[str, Any]] = None,
        user_id: Optional[str] = None,
        session_id: Optional[str] = None
    ) -> ClassificationResult:
        """Classify a query into an intent category"""
        
        start_time = time.time()
        
        # Check cache first
        if self.settings.CACHE_CLASSIFICATION_RESULTS:
            cache_key = self._get_cache_key(query, context)
            if cache_key in self.cache:
                logger.info(f"Cache hit for query: {query[:50]}...")
                return self.cache[cache_key]
        
        try:
            # Step 1: Keyword-based classification
            keyword_scores = self._classify_by_keywords(query)
            
            # Step 2: Pattern-based classification
            pattern_scores = self._classify_by_patterns(query)
            
            # Step 3: Context analysis (if available)
            context_scores = self._analyze_context(context) if context else {}
            
            # Step 4: LLM-based classification (if enabled)
            llm_scores = {}
            llm_reasoning = ""
            if self.settings.ENABLE_LLM_CLASSIFICATION:
                llm_result = await self._classify_with_llm(query, context)
                llm_scores = llm_result.get("scores", {})
                llm_reasoning = llm_result.get("reasoning", "")
            
            # Step 5: Combine all classification methods
            final_scores = self._combine_scores(
                keyword_scores, pattern_scores, context_scores, llm_scores
            )
            
            # Step 6: Determine final intent and confidence
            intent, confidence = self._determine_final_intent(final_scores)
            
            # Step 7: Generate reasoning
            reasoning = self._generate_reasoning(
                query, intent, confidence, keyword_scores, 
                pattern_scores, llm_reasoning
            )
            
            # Create result
            processing_time = int((time.time() - start_time) * 1000)
            
            result = ClassificationResult(
                intent=intent,
                confidence=confidence,
                reasoning=reasoning,
                metadata={
                    "keyword_scores": keyword_scores,
                    "pattern_scores": pattern_scores,
                    "context_scores": context_scores,
                    "llm_scores": llm_scores,
                    "final_scores": final_scores,
                    "user_id": user_id,
                    "session_id": session_id
                },
                processing_time_ms=processing_time
            )
            
            # Cache result
            if self.settings.CACHE_CLASSIFICATION_RESULTS:
                self.cache[cache_key] = result
                
            logger.info(f"Classified query: {intent} ({confidence:.2f}) in {processing_time}ms")
            return result
            
        except Exception as e:
            logger.error(f"Classification error: {str(e)}")
            # Return fallback classification
            return ClassificationResult(
                intent="general",
                confidence=0.1,
                reasoning=f"Classification failed: {str(e)}. Defaulting to general.",
                metadata={"error": str(e)},
                processing_time_ms=int((time.time() - start_time) * 1000)
            )
    
    def _classify_by_keywords(self, query: str) -> Dict[str, float]:
        """Classify query based on keyword matching"""
        query_lower = query.lower()
        scores = {}
        
        for intent in self.settings.INTENT_CATEGORIES:
            score = 0.0
            keyword_attr = f"{intent.upper()}_KEYWORDS"
            keywords = getattr(self.settings, keyword_attr, [])
            
            for keyword in keywords:
                if keyword.lower() in query_lower:
                    # Weight longer keywords more heavily
                    weight = len(keyword.split()) * 0.2 + 0.8
                    score += weight
            
            # Normalize score
            scores[intent] = min(score / max(len(keywords), 1), 1.0)
        
        return scores
    
    def _classify_by_patterns(self, query: str) -> Dict[str, float]:
        """Classify query based on regex pattern matching"""
        scores = {}
        
        for intent in self.settings.INTENT_CATEGORIES:
            score = 0.0
            pattern_attr = f"{intent.upper()}_PATTERNS"
            patterns = getattr(self.settings, pattern_attr, [])
            
            for pattern in patterns:
                try:
                    if re.search(pattern, query, re.IGNORECASE):
                        score += 1.0
                except re.error:
                    logger.warning(f"Invalid regex pattern: {pattern}")
            
            # Normalize score
            scores[intent] = min(score / max(len(patterns), 1), 1.0)
        
        return scores
    
    def _analyze_context(self, context: Dict[str, Any]) -> Dict[str, float]:
        """Analyze context for classification hints"""
        if not context:
            return {}
        
        scores = {intent: 0.0 for intent in self.settings.INTENT_CATEGORIES}
        
        # Check for previous messages in conversation
        if "previous_messages" in context:
            for msg in context["previous_messages"][-3:]:  # Last 3 messages
                if isinstance(msg, dict) and "content" in msg:
                    content = msg["content"].lower()
                    
                    # Look for intent keywords in context
                    if any(word in content for word in ["error", "bug", "issue"]):
                        scores["bug_report"] += 0.3
                    elif any(word in content for word in ["feature", "request", "add"]):
                        scores["feature_request"] += 0.3
                    elif any(word in content for word in ["how", "tutorial", "guide"]):
                        scores["training"] += 0.3
        
        # Check user domain/role
        if "user_domain" in context:
            domain = context["user_domain"].lower()
            if domain == "support":
                scores["bug_report"] += 0.2
            elif domain == "product":
                scores["feature_request"] += 0.2
            elif domain == "engineering":
                scores["training"] += 0.2
        
        return scores
    
    async def _classify_with_llm(self, query: str, context: Optional[Dict[str, Any]]) -> Dict[str, Any]:
        """Use LLM for classification"""
        
        prompt = self._build_classification_prompt(query, context)
        
        try:
            if self.settings.LLM_PROVIDER == "ollama":
                return await self._classify_with_ollama(prompt)
            else:
                return await self._classify_with_openai(prompt)
        except Exception as e:
            logger.error(f"LLM classification failed: {str(e)}")
            return {"scores": {}, "reasoning": f"LLM classification failed: {str(e)}"}
    
    def _build_classification_prompt(self, query: str, context: Optional[Dict[str, Any]]) -> str:
        """Build prompt for LLM classification"""
        
        intent_descriptions = []
        for intent_cat in IntentCategory:
            definition = INTENT_DEFINITIONS[intent_cat]
            intent_descriptions.append(
                f"- {definition.intent}: {definition.description}"
            )
        
        examples = []
        for intent_cat in IntentCategory:
            definition = INTENT_DEFINITIONS[intent_cat]
            for example in definition.examples[:2]:  # Limit examples
                examples.append(f"  '{example}' -> {definition.intent}")
        
        context_str = ""
        if context:
            context_str = f"\nContext: {json.dumps(context, indent=2)}"
        
        prompt = f"""
Classify the following user query into one of these intent categories:

Intent Categories:
{chr(10).join(intent_descriptions)}

Examples:
{chr(10).join(examples)}

Query to classify: "{query}"{context_str}

Please respond with JSON in this exact format:
{{
  "intent": "bug_report|feature_request|training|general",
  "confidence": 0.85,
  "reasoning": "Brief explanation of why this classification was chosen",
  "scores": {{
    "bug_report": 0.1,
    "feature_request": 0.0,
    "training": 0.0,
    "general": 0.9
  }}
}}

Consider:
1. Keywords and phrases that indicate intent
2. Question structure and tone
3. Context from conversation history
4. Specific technical terms or error messages
"""
        return prompt
    
    async def _classify_with_ollama(self, prompt: str) -> Dict[str, Any]:
        """Use Ollama for classification"""
        
        try:
            response = await self.ollama_client.post(
                f"{self.settings.OLLAMA_BASE_URL}/api/generate",
                json={
                    "model": self.settings.LLM_MODEL,
                    "prompt": prompt,
                    "stream": False,
                    "options": {
                        "temperature": 0.1,  # Low temperature for consistent classification
                        "top_p": 0.9
                    }
                }
            )
            
            if response.status_code == 200:
                result = response.json()
                response_text = result.get("response", "")
                
                # Try to parse JSON from response
                try:
                    # Extract JSON from response (may have extra text)
                    json_start = response_text.find('{')
                    json_end = response_text.rfind('}') + 1
                    if json_start >= 0 and json_end > json_start:
                        json_str = response_text[json_start:json_end]
                        return json.loads(json_str)
                except json.JSONDecodeError:
                    logger.warning("Failed to parse LLM JSON response")
                
                # Fallback: extract intent from text
                return self._extract_intent_from_text(response_text)
            else:
                logger.error(f"Ollama API error: {response.status_code}")
                return {"scores": {}, "reasoning": "Ollama API error"}
                
        except Exception as e:
            logger.error(f"Ollama classification error: {str(e)}")
            return {"scores": {}, "reasoning": f"Ollama error: {str(e)}"}
    
    async def _classify_with_openai(self, prompt: str) -> Dict[str, Any]:
        """Use OpenAI for classification"""
        
        try:
            response = await self.openai_client.chat.completions.create(
                model=self.settings.OPENAI_MODEL,
                messages=[
                    {"role": "system", "content": "You are an expert at classifying user queries into intent categories. Always respond with valid JSON."},
                    {"role": "user", "content": prompt}
                ],
                temperature=0.1,
                max_tokens=500
            )
            
            response_text = response.choices[0].message.content
            
            # Parse JSON response
            try:
                return json.loads(response_text)
            except json.JSONDecodeError:
                return self._extract_intent_from_text(response_text)
                
        except Exception as e:
            logger.error(f"OpenAI classification error: {str(e)}")
            return {"scores": {}, "reasoning": f"OpenAI error: {str(e)}"}
    
    def _extract_intent_from_text(self, text: str) -> Dict[str, Any]:
        """Extract intent from text response when JSON parsing fails"""
        text_lower = text.lower()
        
        # Look for intent mentions
        for intent in self.settings.INTENT_CATEGORIES:
            if intent in text_lower:
                return {
                    "intent": intent,
                    "confidence": 0.7,
                    "reasoning": f"Extracted '{intent}' from LLM response",
                    "scores": {intent: 0.7}
                }
        
        return {
            "intent": "general",
            "confidence": 0.5,
            "reasoning": "Could not parse LLM response",
            "scores": {"general": 0.5}
        }
    
    def _combine_scores(
        self, 
        keyword_scores: Dict[str, float],
        pattern_scores: Dict[str, float],
        context_scores: Dict[str, float],
        llm_scores: Dict[str, float]
    ) -> Dict[str, float]:
        """Combine scores from different classification methods"""
        
        final_scores = {}
        
        for intent in self.settings.INTENT_CATEGORIES:
            # Weighted combination of different methods
            keyword_weight = 0.3 if self.settings.ENABLE_KEYWORD_ANALYSIS else 0.0
            pattern_weight = 0.2 if self.settings.ENABLE_PATTERN_MATCHING else 0.0
            context_weight = 0.1 if self.settings.ENABLE_CONTEXT_ANALYSIS else 0.0
            llm_weight = 0.4 if self.settings.ENABLE_LLM_CLASSIFICATION else 0.0
            
            # Normalize weights if some methods are disabled
            total_weight = keyword_weight + pattern_weight + context_weight + llm_weight
            if total_weight > 0:
                keyword_weight /= total_weight
                pattern_weight /= total_weight
                context_weight /= total_weight
                llm_weight /= total_weight
            
            score = (
                keyword_scores.get(intent, 0.0) * keyword_weight +
                pattern_scores.get(intent, 0.0) * pattern_weight +
                context_scores.get(intent, 0.0) * context_weight +
                llm_scores.get(intent, 0.0) * llm_weight
            )
            
            final_scores[intent] = score
        
        return final_scores
    
    def _determine_final_intent(self, scores: Dict[str, float]) -> Tuple[str, float]:
        """Determine final intent and confidence from scores"""
        
        if not scores:
            return "general", 0.1
        
        # Find intent with highest score
        best_intent = max(scores.keys(), key=lambda k: scores[k])
        best_score = scores[best_intent]
        
        # Calculate confidence based on score and separation from second best
        sorted_scores = sorted(scores.values(), reverse=True)
        
        if len(sorted_scores) > 1:
            score_gap = sorted_scores[0] - sorted_scores[1]
            confidence = min(best_score + (score_gap * 0.2), 1.0)
        else:
            confidence = best_score
        
        # Apply confidence boosting if enabled
        if self.settings.ENABLE_CONFIDENCE_BOOSTING and confidence > 0.7:
            confidence = min(confidence * 1.1, 1.0)
        
        return best_intent, confidence
    
    def _generate_reasoning(
        self, 
        query: str, 
        intent: str, 
        confidence: float,
        keyword_scores: Dict[str, float],
        pattern_scores: Dict[str, float],
        llm_reasoning: str
    ) -> str:
        """Generate human-readable reasoning for classification"""
        
        reasoning_parts = []
        
        # Add confidence level
        if confidence >= self.settings.HIGH_CONFIDENCE_THRESHOLD:
            reasoning_parts.append(f"High confidence classification as '{intent}'")
        elif confidence >= self.settings.MIN_CONFIDENCE_THRESHOLD:
            reasoning_parts.append(f"Moderate confidence classification as '{intent}'")
        else:
            reasoning_parts.append(f"Low confidence classification as '{intent}'")
        
        # Add method contributions
        methods_used = []
        
        if keyword_scores.get(intent, 0.0) > 0.3:
            methods_used.append("keyword matching")
        
        if pattern_scores.get(intent, 0.0) > 0.3:
            methods_used.append("pattern recognition")
        
        if llm_reasoning and "error" not in llm_reasoning.lower():
            methods_used.append("LLM analysis")
        
        if methods_used:
            reasoning_parts.append(f"based on {', '.join(methods_used)}")
        
        # Add LLM reasoning if available
        if llm_reasoning and "error" not in llm_reasoning.lower():
            reasoning_parts.append(f"LLM reasoning: {llm_reasoning}")
        
        return ". ".join(reasoning_parts) + "."
    
    def _get_cache_key(self, query: str, context: Optional[Dict[str, Any]]) -> str:
        """Generate cache key for query and context"""
        
        context_str = json.dumps(context, sort_keys=True) if context else ""
        combined = f"{query}|{context_str}"
        return hashlib.md5(combined.encode()).hexdigest()
    
    async def get_intent_definitions(self) -> List[IntentDefinition]:
        """Get all intent definitions"""
        return [definition for definition in INTENT_DEFINITIONS.values()]
    
    async def get_intent_examples(self, intent: str) -> List[str]:
        """Get examples for specific intent"""
        for intent_cat in IntentCategory:
            if intent_cat.value == intent:
                return INTENT_DEFINITIONS[intent_cat].examples
        
        raise ValueError(f"Unknown intent: {intent}")
    
    async def process_feedback(
        self, 
        classification_id: str, 
        correct_intent: str, 
        confidence_rating: float
    ):
        """Process feedback for model improvement"""
        
        logger.info(f"Processing feedback for {classification_id}: {correct_intent} (rating: {confidence_rating})")
        
        # In a production system, this would:
        # 1. Store feedback in database
        # 2. Trigger model retraining if enough feedback accumulated
        # 3. Update classification weights based on feedback
        
        # For now, just log
        if confidence_rating < 0.5:
            logger.warning(f"Low confidence feedback received for {classification_id}")
        elif confidence_rating > 0.8:
            logger.info(f"High confidence feedback received for {classification_id}") 
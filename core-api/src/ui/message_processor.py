"""
Message Processor for Chat API Service
Handles RAG response generation, context management, and domain-aware processing.
"""

import asyncio
from typing import List, Dict, Any, Optional
from datetime import datetime

from domain_client import DomainVectorClient
from session_manager import SessionManager
from database import ChatSession
from config import Settings


class MessageProcessor:
    """Processes chat messages and generates RAG responses"""
    
    def __init__(self, domain_client: DomainVectorClient, settings: Settings):
        self.domain_client = domain_client
        self.settings = settings
        self.session_manager = SessionManager()
    
    async def process_message(self, message: str, session: ChatSession, user, 
                            context: Optional[Dict[str, Any]], db) -> Dict[str, Any]:
        """Process user message and generate response"""
        
        # Store user message
        user_message = self.session_manager.add_message(
            session_id=session.session_id,
            message_type="user",
            content=message,
            metadata={"context": context} if context else None,
            db=db
        )
        
        try:
            # Get conversation context
            conversation_context = self.session_manager.get_recent_context(
                session.session_id, db, self.settings.MAX_CONTEXT_MESSAGES
            )
            
            # Determine domain for search
            search_domain = await self._determine_search_domain(message, session.domain, user)
            
            # Perform RAG search
            search_results = await self._perform_rag_search(message, search_domain, user)
            
            # Generate response
            response_text = await self._generate_response(
                message, search_results, conversation_context, search_domain
            )
            
            # Calculate confidence score
            confidence = self._calculate_confidence(search_results, response_text)
            
            # Generate suggested actions
            suggested_actions = self._generate_suggestions(message, search_results, search_domain)
            
            # Store assistant response
            response_metadata = {
                "search_domain": search_domain,
                "sources_count": len(search_results.get("results", [])),
                "confidence": confidence,
                "search_error": search_results.get("error"),
                "suggested_actions": suggested_actions
            }
            
            assistant_message = self.session_manager.add_message(
                session_id=session.session_id,
                message_type="assistant",
                content=response_text,
                metadata=response_metadata,
                db=db
            )
            
            # Format response
            return {
                "response": response_text,
                "session_id": session.session_id,
                "domain": search_domain,
                "confidence": confidence,
                "sources": self._format_sources(search_results.get("results", [])),
                "suggested_actions": suggested_actions
            }
            
        except Exception as e:
            # Store error response
            error_response = f"I apologize, but I encountered an error processing your message: {str(e)}"
            
            self.session_manager.add_message(
                session_id=session.session_id,
                message_type="assistant",
                content=error_response,
                metadata={"error": str(e)},
                db=db
            )
            
            return {
                "response": error_response,
                "session_id": session.session_id,
                "domain": session.domain,
                "confidence": 0.0,
                "sources": [],
                "suggested_actions": ["Please try rephrasing your question"]
            }
    
    async def _determine_search_domain(self, message: str, session_domain: str, user) -> str:
        """Determine which domain to search based on message content"""
        if not self.settings.ENABLE_DOMAIN_AUTO_DETECTION:
            return session_domain
        
        # Use domain classification from client
        suggested_domain = await self.domain_client.classify_domain(message)
        
        # Check if user has access to suggested domain
        if suggested_domain in user.allowed_domains:
            return suggested_domain
        
        # Fallback to session domain
        return session_domain
    
    async def _perform_rag_search(self, query: str, domain: str, user) -> Dict[str, Any]:
        """Perform RAG search in the determined domain"""
        # First try domain-specific search
        results = await self.domain_client.search_domain(domain, query, top_k=10)
        
        # If no good results found, try cross-domain search
        if (results.get("total_found", 0) == 0 or 
            self._get_max_similarity(results.get("results", [])) < self.settings.MIN_CONFIDENCE_THRESHOLD):
            
            # Try searching across all user's accessible domains
            cross_domain_results = await self.domain_client.auto_search(
                query, domains=user.allowed_domains, top_k=15
            )
            
            # Use cross-domain results if they're better
            if (cross_domain_results.get("total_found", 0) > results.get("total_found", 0) or
                self._get_max_similarity(cross_domain_results.get("results", [])) > 
                self._get_max_similarity(results.get("results", []))):
                results = cross_domain_results
        
        return results
    
    def _get_max_similarity(self, results: List[Dict]) -> float:
        """Get maximum similarity score from results"""
        if not results:
            return 0.0
        return max(result.get("similarity", 0.0) for result in results)
    
    async def _generate_response(self, query: str, search_results: Dict[str, Any], 
                               context: List[Dict[str, Any]], domain: str) -> str:
        """Generate response based on search results and context"""
        
        results = search_results.get("results", [])
        error = search_results.get("error")
        
        if error:
            return f"I encountered an issue searching for information: {error}. Please try rephrasing your question."
        
        if not results:
            return self._generate_no_results_response(query, domain)
        
        # Get domain-specific response style
        response_style = self._get_domain_response_style(domain)
        
        # Build response from search results
        response_parts = []
        
        # Add greeting with domain context
        response_parts.append(response_style["greeting"])
        
        # Add main response based on top results
        top_results = results[:3]  # Use top 3 results
        
        if len(top_results) == 1:
            # Single result
            result = top_results[0]
            content = result.get("content", "")
            response_parts.append(f"Based on the information I found: {content}")
        else:
            # Multiple results
            response_parts.append("Based on the information I found:")
            for i, result in enumerate(top_results, 1):
                content = result.get("content", "")
                response_parts.append(f"{i}. {content}")
        
        # Add domain-specific closing
        response_parts.append(response_style["closing"])
        
        return "\n\n".join(response_parts)
    
    def _get_domain_response_style(self, domain: str) -> Dict[str, str]:
        """Get domain-specific response styling"""
        styles = {
            "support": {
                "greeting": "I'll help you troubleshoot this issue.",
                "closing": "If this doesn't resolve your issue, please let me know and I can help you escalate to our support team."
            },
            "sales": {
                "greeting": "I can provide information about our product capabilities.",
                "closing": "Would you like me to connect you with our sales team for a detailed demo or pricing discussion?"
            },
            "engineering": {
                "greeting": "Here's the technical information you requested.",
                "closing": "Let me know if you need more technical details or code examples."
            },
            "product": {
                "greeting": "I can help with product information and planning.",
                "closing": "Is there anything specific about our product roadmap or features you'd like to know more about?"
            },
            "general": {
                "greeting": "Here's what I found for your question.",
                "closing": "Is there anything else you'd like to know?"
            }
        }
        
        return styles.get(domain, styles["general"])
    
    def _generate_no_results_response(self, query: str, domain: str) -> str:
        """Generate response when no search results are found"""
        domain_specific_responses = {
            "support": "I couldn't find a direct answer to your issue in our knowledge base. Let me connect you with our support team for personalized assistance.",
            "sales": "I don't have specific information about that product feature. Our sales team can provide detailed information and answer any questions you have.",
            "engineering": "I couldn't find technical documentation for that topic. You might want to check our developer portal or contact our engineering team.",
            "product": "I don't have information about that product aspect. Our product team would be the best resource for detailed information.",
            "general": "I couldn't find specific information about that topic. Could you try rephrasing your question or be more specific about what you're looking for?"
        }
        
        return domain_specific_responses.get(domain, domain_specific_responses["general"])
    
    def _calculate_confidence(self, search_results: Dict[str, Any], response: str) -> float:
        """Calculate confidence score for the response"""
        results = search_results.get("results", [])
        
        if not results:
            return 0.1
        
        # Base confidence on similarity scores
        similarities = [result.get("similarity", 0.0) for result in results]
        avg_similarity = sum(similarities) / len(similarities)
        max_similarity = max(similarities)
        
        # Boost confidence if multiple results agree
        if len(results) >= 3:
            confidence = (avg_similarity * 0.6) + (max_similarity * 0.4)
        else:
            confidence = max_similarity * 0.8
        
        # Cap confidence at 0.95
        return min(confidence, 0.95)
    
    def _generate_suggestions(self, query: str, search_results: Dict[str, Any], domain: str) -> List[str]:
        """Generate suggested follow-up actions"""
        if not self.settings.ENABLE_SUGGESTIONS:
            return []
        
        suggestions = []
        results = search_results.get("results", [])
        
        if not results:
            # No results suggestions
            suggestions.extend([
                "Try rephrasing your question",
                "Be more specific about what you're looking for",
                f"Search in a different domain"
            ])
        else:
            # Good results suggestions
            domain_suggestions = {
                "support": [
                    "Contact support team if this doesn't resolve your issue",
                    "Check our status page for any ongoing issues",
                    "View our troubleshooting guide"
                ],
                "sales": [
                    "Schedule a demo with our sales team",
                    "View pricing information",
                    "Compare our features with competitors"
                ],
                "engineering": [
                    "Check our API documentation",
                    "View code examples",
                    "Join our developer community"
                ],
                "product": [
                    "View our product roadmap",
                    "Submit a feature request",
                    "Check user feedback and reviews"
                ]
            }
            
            suggestions.extend(domain_suggestions.get(domain, [
                "Ask a follow-up question",
                "Search for related topics"
            ]))
        
        return suggestions[:3]  # Limit to 3 suggestions
    
    def _format_sources(self, results: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """Format search results as sources"""
        formatted_sources = []
        
        for result in results:
            source = {
                "id": result.get("id"),
                "content": result.get("content", "")[:200] + "..." if len(result.get("content", "")) > 200 else result.get("content", ""),
                "similarity": result.get("similarity", 0.0),
                "domain": result.get("domain"),
                "metadata": result.get("metadata", {})
            }
            
            # Add source type and title if available
            metadata = result.get("metadata", {})
            source["source_type"] = metadata.get("source_type", "unknown")
            source["title"] = metadata.get("title", "Untitled")
            
            formatted_sources.append(source)
        
        return formatted_sources 
"""
LLM Service - Ollama Integration for Response Generation
"""

import json
import requests
from typing import List, Dict, Optional
import logging

logger = logging.getLogger(__name__)

class LLMService:
    """Service for interacting with Ollama LLM"""
    
    def __init__(self, base_url: str = "http://ollama:11434"):
        self.base_url = base_url
        self.model = "llama3.1:8b"  # Use the better model we just installed
        
    def generate_response(
        self, 
        query: str, 
        context: str, 
        sources: List[Dict],
        intent: str = "general_query"
    ) -> str:
        """Generate a concise response using Ollama with proper citations"""
        
        # Create a focused prompt for concise responses
        prompt = self._create_concise_prompt(query, context, sources, intent)
        
        try:
            response = requests.post(
                f"{self.base_url}/api/generate",
                json={
                    "model": self.model,
                    "prompt": prompt,
                    "stream": False,
                    "options": {
                        "temperature": 0.7,
                        "top_p": 0.9,
                        "max_tokens": 300,  # Reduced for more concise responses
                        "stop": ["Human:", "Assistant:", "\n\n---", "Sources:", "References:"]
                    }
                },
                timeout=30
            )
            
            if response.status_code == 200:
                result = response.json()
                raw_response = result.get("response", "").strip()
                # Post-process to ensure proper citation formatting
                return self._enhance_citations(raw_response, sources)
            else:
                logger.error(f"Ollama API error: {response.status_code}")
                return self._fallback_response(query, context, sources)
                
        except Exception as e:
            logger.error(f"LLM generation failed: {e}")
            return self._fallback_response(query, context, sources)
    
    def _create_concise_prompt(self, query: str, context: str, sources: List[Dict], intent: str) -> str:
        """Create a focused prompt for concise responses with clickable citations"""
        
        # Source information for context with numbered citation format
        source_context = ""
        citation_guide = ""
        if sources:
            source_context = "\n\nAvailable sources for reference:\n"
            citation_guide = "\n\nCITATION FORMAT - Use numbered citations that will be clickable:\n"
            
            for i, source in enumerate(sources[:3], 1):
                title = source['title']
                citation_id = source.get('citation_id', f'cite_{i}')
                
                source_context += f"[{i}] {title}\n"
                # Use full content for better understanding
                content = source.get('full_content', source.get('excerpt', source.get('preview', '')))
                if len(content) > 500:
                    content = content[:500] + "..."
                source_context += f"    {content}\n\n"
                
                # Provide numbered citation format
                citation_guide += f"- To reference source {i} ({title}): use '[{i}]' at the end of relevant sentences\n"
        
        # Intent-specific instructions for concise responses
        intent_instructions = {
            "bug_report": "Provide a concise analysis of the issue and key troubleshooting steps.",
            "feature_request": "Give a brief response about the request and mention any existing alternatives.",
            "training": "Provide a clear, concise explanation or step-by-step guidance.",
            "general_query": "Give a direct, helpful answer to the question."
        }
        
        instruction = intent_instructions.get(intent, intent_instructions["general_query"])
        
        prompt = f"""You are an AI assistant providing concise, helpful responses. {instruction}

User Question: {query}

Context Information:
{context}
{source_context}{citation_guide}

IMPORTANT INSTRUCTIONS:
- Provide a direct, concise answer (2-4 sentences maximum)
- Focus on answering the specific question asked
- When referencing information, use NUMBERED citations in square brackets (e.g., "AI is a field of computer science [1]" or "According to the research [2]")
- ALWAYS use the numbered format [1], [2], [3] that corresponds to the sources listed above
- Place citations at the end of sentences or after specific claims
- These numbered citations will be clickable in the interface to show source details
- Do NOT include a separate "Sources" or "References" section
- Do NOT repeat the full source content in your response
- Be helpful but brief - the user will see detailed sources separately
- Use a professional, conversational tone

Response:"""
        
        return prompt
    
    def _enhance_citations(self, response: str, sources: List[Dict]) -> str:
        """Enhance response with numbered citations linked to source citation_ids"""
        if not sources:
            return response
        
        # The LLM should already be generating [1], [2], [3] format
        # We just need to ensure they're properly formatted for frontend linking
        import re
        
        # Find all numbered citations in the response
        citation_pattern = r'\[(\d+)\]'
        
        def replace_citation(match):
            number = int(match.group(1))
            # Make sure the number corresponds to a valid source
            if 1 <= number <= len(sources):
                source = sources[number - 1]  # Convert to 0-based index
                citation_id = source.get('citation_id', f'cite_{number}')
                # Return the citation with a data attribute for frontend linking
                return f'<cite data-citation-id="{citation_id}" data-source-index="{number-1}">[{number}]</cite>'
            else:
                # Return original if number is out of range
                return match.group(0)
        
        enhanced_response = re.sub(citation_pattern, replace_citation, response)
        return enhanced_response
    
    def _fallback_response(self, query: str, context: str, sources: List[Dict]) -> str:
        """Concise fallback response when LLM is unavailable"""
        if not context.strip():
            return "I couldn't find specific information to answer your question. Please try rephrasing or providing more details."
        
        # Extract key information for a concise response
        sentences = context.split('. ')
        key_info = '. '.join(sentences[:2])  # First 2 sentences
        
        if len(key_info) > 200:
            key_info = key_info[:200] + "..."
        
        response = f"Based on the available information: {key_info}"
        
        if sources and len(sources) > 0:
            response += f" (Source: {sources[0]['title']})"
        
        return response
    
    def is_available(self) -> bool:
        """Check if Ollama service is available"""
        try:
            response = requests.get(f"{self.base_url}/api/tags", timeout=5)
            return response.status_code == 200
        except:
            return False

# Global instance
llm_service = LLMService()

def get_llm_service() -> LLMService:
    """Get the global LLM service instance"""
    return llm_service 
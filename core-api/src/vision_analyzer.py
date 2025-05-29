"""
Vision Analyzer Service - Analyze images for better contextual descriptions
"""

import base64
import requests
from typing import Dict, List, Optional
import logging
from PIL import Image
import io

logger = logging.getLogger(__name__)

class VisionAnalyzer:
    """Analyze images to provide better contextual descriptions"""
    
    def __init__(self, ollama_base_url: str = "http://ollama:11434"):
        self.ollama_base_url = ollama_base_url
        self.vision_model = "llama3.2-vision:11b"  # Multimodal model
        self.available = False
        self._check_vision_model()
    
    def _check_vision_model(self):
        """Check if vision model is available"""
        try:
            response = requests.get(f"{self.ollama_base_url}/api/tags", timeout=5)
            if response.status_code == 200:
                models = response.json().get("models", [])
                available_models = [model["name"] for model in models]
                
                # Check for any vision-capable model
                vision_models = [
                    "llama3.2-vision:11b",
                    "llama3.2-vision:90b", 
                    "llava:7b",
                    "llava:13b",
                    "moondream:1.8b"
                ]
                
                for model in vision_models:
                    if model in available_models:
                        self.vision_model = model
                        self.available = True
                        logger.info(f"Vision model available: {self.vision_model}")
                        return
                
                # Try to pull a lightweight vision model
                logger.info("No vision model found. Attempting to pull moondream:1.8b...")
                self._pull_vision_model("moondream:1.8b")
                
        except Exception as e:
            logger.error(f"Error checking vision model: {e}")
            self.available = False
    
    def _pull_vision_model(self, model_name: str):
        """Pull a vision model if none available"""
        try:
            response = requests.post(
                f"{self.ollama_base_url}/api/pull",
                json={"name": model_name},
                timeout=600  # 10 minutes for model download
            )
            
            if response.status_code == 200:
                self.vision_model = model_name
                self.available = True
                logger.info(f"Successfully pulled vision model: {model_name}")
            
        except Exception as e:
            logger.error(f"Failed to pull vision model {model_name}: {e}")
    
    def analyze_image(self, image_data: bytes, context_hint: str = "") -> Dict[str, str]:
        """Analyze an image and return contextual description"""
        if not self.available:
            return {
                "description": "Image analysis not available",
                "context_tags": [],
                "ui_elements": [],
                "content_type": "unknown"
            }
        
        try:
            # Convert image to base64
            image_b64 = base64.b64encode(image_data).decode('utf-8')
            
            # Create analysis prompt - more specific for login vs document detection
            prompt = f"""Analyze this image carefully. This could be either a user interface screenshot OR a document/paper image.

First, determine what type of image this is:
- Is this a computer/web interface screenshot (login pages, dashboards, forms)?
- Is this a document, paper, or file (PDFs, text documents, images of physical papers)?

If it's a user interface screenshot, identify:
1. What type of interface: login page, dashboard, form, settings, etc.
2. Key UI elements: buttons, input fields, menus, navigation
3. Any visible text or labels
4. Primary purpose of this screen

If it's a document/paper, identify:
1. Type of document (paper, PDF, form, etc.)
2. Any visible text or content
3. Purpose or subject matter

Be very specific about login pages - they must have clear login forms with username/password fields.

Context hint: {context_hint}

Provide a clear, accurate description that distinguishes between interface screenshots and document images."""
            
            # Send to vision model
            response = requests.post(
                f"{self.ollama_base_url}/api/generate",
                json={
                    "model": self.vision_model,
                    "prompt": prompt,
                    "images": [image_b64],
                    "stream": False,
                    "options": {
                        "temperature": 0.1,  # Very low temperature for consistent analysis
                        "max_tokens": 300
                    }
                },
                timeout=45
            )
            
            if response.status_code == 200:
                result = response.json()
                description = result.get("response", "").strip()
                
                # Extract key information with strict login detection
                analysis = self._parse_vision_response_strict(description)
                logger.info(f"Vision analysis complete: {analysis['content_type']} - {description[:100]}...")
                return analysis
            
        except Exception as e:
            logger.error(f"Vision analysis failed: {e}")
        
        # Fallback analysis
        return {
            "description": "Interface screenshot",
            "context_tags": ["interface"],
            "ui_elements": [],
            "content_type": "interface"
        }
    
    def _parse_vision_response_strict(self, description: str) -> Dict[str, str]:
        """Parse vision model response with strict content type detection"""
        description_lower = description.lower()
        
        # First check if this is clearly a document/paper (explicit rejection)
        document_indicators = [
            "document", "paper", "pdf", "file", "text document", "written",
            "pencil", "pen", "handwriting", "printed", "page", "sheet",
            "letter", "memo", "report document", "physical paper"
        ]
        
        is_document = any(indicator in description_lower for indicator in document_indicators)
        
        # Check for UI/interface indicators
        interface_indicators = [
            "screen", "interface", "webpage", "browser", "application", "app",
            "button", "click", "field", "input", "form", "window", "display"
        ]
        
        is_interface = any(indicator in description_lower for indicator in interface_indicators)
        
        # Determine content type with strict rules
        content_type = "unknown"
        
        if is_document and not is_interface:
            # Clearly a document, not an interface
            content_type = "document"
            logger.info(f"STRICT VISION: Classified as document due to: {[ind for ind in document_indicators if ind in description_lower]}")
        
        elif is_interface or not is_document:
            # Likely an interface - now determine what kind
            
            # STRICT login page detection - must have explicit login elements
            login_strong_indicators = [
                "login form", "sign in form", "username field", "password field",
                "login page", "authentication form", "username and password",
                "login screen", "sign in screen"
            ]
            
            login_weak_indicators = ["login", "sign in", "password", "username", "authenticate"]
            
            has_strong_login = any(indicator in description_lower for indicator in login_strong_indicators)
            has_weak_login = any(indicator in description_lower for indicator in login_weak_indicators)
            
            if has_strong_login:
                content_type = "login_page"
                logger.info(f"STRICT VISION: Strong login page detection: {[ind for ind in login_strong_indicators if ind in description_lower]}")
            
            elif has_weak_login and is_interface and not is_document:
                # Only consider weak indicators if clearly an interface and not a document
                content_type = "login_page"
                logger.info(f"STRICT VISION: Weak login page detection (interface confirmed): {[ind for ind in login_weak_indicators if ind in description_lower]}")
            
            elif any(word in description_lower for word in ["dashboard", "overview", "summary", "home page"]):
                content_type = "dashboard"
            elif any(word in description_lower for word in ["form", "input fields", "submit"]) and not has_weak_login:
                content_type = "form"
            elif any(word in description_lower for word in ["menu", "navigation", "sidebar", "nav"]):
                content_type = "navigation"
            elif any(word in description_lower for word in ["settings", "configuration", "preferences", "config"]):
                content_type = "settings"
            elif any(word in description_lower for word in ["table", "list", "data", "report table"]):
                content_type = "data_view"
            elif is_interface:
                content_type = "interface"
            else:
                content_type = "unknown"
        
        # Extract context tags based on content type
        context_tags = []
        if content_type == "login_page":
            context_tags = ["login", "authentication", "interface"]
        elif content_type == "document":
            context_tags = ["document", "paper", "text"]
        elif content_type in ["dashboard", "form", "navigation", "settings", "data_view", "interface"]:
            context_tags = ["interface", content_type.replace("_", "")]
        
        # Extract UI elements mentioned (only for interfaces, not documents)
        ui_elements = []
        if content_type != "document":
            ui_keywords = ["button", "field", "menu", "link", "form", "table", "input", "dropdown"]
            for keyword in ui_keywords:
                if keyword in description_lower:
                    ui_elements.append(keyword)
        
        logger.info(f"STRICT VISION RESULT: content_type={content_type}, is_document={is_document}, is_interface={is_interface}")
        
        return {
            "description": description,
            "context_tags": context_tags,
            "ui_elements": ui_elements,
            "content_type": content_type
        }
    
    def enhance_image_metadata(self, images_data: List[Dict]) -> List[Dict]:
        """Enhance existing image metadata with vision analysis"""
        if not self.available:
            return images_data
        
        enhanced_images = []
        
        for img_data in images_data:
            enhanced_img = img_data.copy()
            
            try:
                # Get image data (assuming it's stored as base64 or URL)
                if 'data' in img_data and img_data['data'].startswith('data:image'):
                    # Extract base64 data
                    b64_data = img_data['data'].split(',')[1]
                    image_bytes = base64.b64decode(b64_data)
                    
                    # Analyze the image
                    analysis = self.analyze_image(image_bytes, img_data.get('alt_text', ''))
                    
                    # Enhance metadata
                    enhanced_img.update({
                        'enhanced_description': analysis['description'],
                        'content_type_detected': analysis['content_type'],
                        'context_tags': analysis['context_tags'],
                        'ui_elements': analysis['ui_elements'],
                        'vision_analyzed': True
                    })
                    
                    # Update alt_text with more descriptive version
                    if analysis['content_type'] != 'unknown':
                        enhanced_img['alt_text'] = f"{analysis['content_type'].replace('_', ' ').title()}: {analysis['description'][:100]}"
                    
                else:
                    enhanced_img['vision_analyzed'] = False
                    
            except Exception as e:
                logger.error(f"Error enhancing image metadata: {e}")
                enhanced_img['vision_analyzed'] = False
            
            enhanced_images.append(enhanced_img)
        
        return enhanced_images
    
    def select_best_image_for_query(self, query: str, available_images: List[Dict]) -> Optional[Dict]:
        """Select the most relevant image for a given query"""
        if not available_images:
            return None
        
        query_lower = query.lower()
        best_image = None
        best_score = 0
        
        # Query intent analysis
        query_intents = {
            "login": ["login", "sign in", "access", "authenticate", "password"],
            "navigation": ["navigate", "menu", "find", "go to", "access"],
            "dashboard": ["dashboard", "overview", "home", "main"],
            "settings": ["settings", "configure", "setup", "preferences"],
            "form": ["fill", "create", "add", "submit", "form"],
            "data": ["view", "see", "check", "report", "list"]
        }
        
        detected_intent = None
        for intent, keywords in query_intents.items():
            if any(keyword in query_lower for keyword in keywords):
                detected_intent = intent
                break
        
        for img in available_images:
            score = 0
            
            # Check if image has vision analysis
            if img.get('vision_analyzed'):
                content_type = img.get('content_type_detected', '')
                context_tags = img.get('context_tags', [])
                
                # Score based on content type match
                if detected_intent and detected_intent in content_type:
                    score += 50
                
                # Score based on context tags
                if detected_intent and detected_intent in context_tags:
                    score += 30
                
                # Score based on description keyword match
                description = img.get('enhanced_description', '').lower()
                query_words = query_lower.split()
                for word in query_words:
                    if len(word) > 3 and word in description:
                        score += 10
            
            else:
                # Fallback to basic alt_text matching
                alt_text = img.get('alt_text', '').lower()
                query_words = query_lower.split()
                for word in query_words:
                    if len(word) > 3 and word in alt_text:
                        score += 5
            
            if score > best_score:
                best_score = score
                best_image = img
        
        logger.info(f"Selected image for query '{query}': {best_image.get('alt_text', 'Unknown')} (score: {best_score})")
        return best_image

# Global instance
vision_analyzer = VisionAnalyzer()

def get_vision_analyzer() -> VisionAnalyzer:
    """Get the global vision analyzer instance"""
    return vision_analyzer 
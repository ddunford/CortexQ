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
        self.model = None  # Will be set automatically
        self.preferred_models = [
            "llama3.1:8b",      # More capable, better reasoning
            "llama3.2:3b",      # Mid-range option
            "llama3.1:7b",      # Alternative capable model
            "llama3.2:1b",      # Lightweight fallback
            "llama2:7b",        # Final fallback
        ]
        self.vision_analyzer = None
        self._initialize_model()
        self._initialize_vision()
        
    def _initialize_model(self):
        """Initialize with the best available model"""
        try:
            available_models = self._get_available_models()
            
            if not available_models:
                logger.warning("No Ollama models found. Attempting to pull default model...")
                self._auto_pull_model("llama3.2:1b")
                available_models = self._get_available_models()
            
            # Select the best available model from preferences
            selected_model = None
            for preferred in self.preferred_models:
                if preferred in available_models:
                    selected_model = preferred
                    break
            
            if selected_model:
                self.model = selected_model
                logger.info(f"LLM Service initialized with model: {self.model}")
            else:
                # Use the first available model
                self.model = available_models[0] if available_models else "llama3.2:1b"
                logger.warning(f"Using fallback model: {self.model}")
                
        except Exception as e:
            logger.error(f"Failed to initialize LLM model: {e}")
            self.model = "llama3.2:1b"  # Safe fallback
    
    def _get_available_models(self) -> List[str]:
        """Get list of available models from Ollama"""
        try:
            response = requests.get(f"{self.base_url}/api/tags", timeout=5)
            if response.status_code == 200:
                data = response.json()
                return [model["name"] for model in data.get("models", [])]
            return []
        except Exception as e:
            logger.error(f"Failed to get available models: {e}")
            return []
    
    def _auto_pull_model(self, model_name: str) -> bool:
        """Automatically pull a model if none are available"""
        try:
            logger.info(f"Auto-pulling model: {model_name}")
            response = requests.post(
                f"{self.base_url}/api/pull",
                json={"name": model_name},
                timeout=300  # 5 minutes for model download
            )
            
            if response.status_code == 200:
                logger.info(f"Successfully pulled model: {model_name}")
                return True
            else:
                logger.error(f"Failed to pull model {model_name}: {response.status_code}")
                return False
                
        except Exception as e:
            logger.error(f"Error pulling model {model_name}: {e}")
            return False
    
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
                # Post-process to ensure clean, professional formatting
                cleaned_response = self._clean_llm_response(raw_response)
                return self._enhance_citations(cleaned_response, sources)
            else:
                logger.error(f"Ollama API error: {response.status_code}")
                return self._fallback_response(query, context, sources)
                
        except Exception as e:
            logger.error(f"LLM generation failed: {e}")
            return self._fallback_response(query, context, sources)
    
    def _create_concise_prompt(self, query: str, context: str, sources: List[Dict], intent: str) -> str:
        """Create a concise prompt focused on direct answers"""
        
        print(f"🔍 DEBUG LLM PROMPT: Creating prompt for query='{query}', intent='{intent}', {len(sources)} sources")
        
        # Extract available images with proper ID format
        image_context = self._extract_image_references(sources, query)
        
        # Base prompt
        prompt = f"""Based on the following context, provide a direct, helpful answer to the user's question.

QUESTION: {query}

CONTEXT:
{context}

IMPORTANT INSTRUCTIONS:
- Give a direct, practical answer
- Use step-by-step format when appropriate
- Include relevant details but keep it concise
- DO NOT include confidence scores or metadata in your response

"""
        
        # Add image instructions only if images are available
        if image_context.strip():
            prompt += f"""
{image_context}

CRITICAL IMAGE USAGE RULES:
- ALWAYS use the exact image syntax provided above when referencing visual elements
- For login screens or interfaces, include the relevant screenshot using the exact format shown
- Example: If showing a login page, use ![Login Screen](screenshot_0_0) 
- Replace generic descriptions with actual image references
- Do NOT use emojis (🔒, 📱, etc.) instead of images

"""
            print(f"✅ DEBUG LLM PROMPT: Added image context to prompt")
        else:
            print(f"❌ DEBUG LLM PROMPT: No image context available")
        
        # Special handling for login-related queries
        if 'login' in query.lower():
            # Look for specific login-related images in the available references
            login_images = []
            for line in image_context.split('\n'):
                if any(keyword in line.lower() for keyword in ['lock', 'login', 'yellow', 'lilac']):
                    login_images.append(line)
            
            prompt += """
FOR LOGIN QUESTIONS: """
            if login_images:
                prompt += f"""Use these specific login-related images:
{chr(10).join(login_images)}

When describing the login process, reference the appropriate image using the EXACT syntax shown above.
"""
                print(f"🔑 DEBUG LLM PROMPT: Found {len(login_images)} login-related images")
            else:
                prompt += """If login screenshots are available, show them in your response using the exact image syntax provided above.
"""
            print(f"🔑 DEBUG LLM PROMPT: Added special login instructions")
        
        prompt += """ANSWER:"""
        
        print(f"🔍 DEBUG LLM PROMPT: Final prompt length: {len(prompt)} characters")
        print(f"🔍 DEBUG LLM PROMPT: Prompt preview:\n{prompt[:500]}...")
        
        return prompt
    
    def _clean_context_text(self, context: str) -> str:
        """Clean up context text to remove search metadata and artifacts"""
        import re
        
        # Remove confidence scores and percentages
        context = re.sub(r'\d+%\s*confidence', '', context)
        
        # Remove document title patterns (lines that look like titles)
        lines = context.split('\n')
        cleaned_lines = []
        
        for line in lines:
            line = line.strip()
            
            # Skip lines that look like document titles or metadata
            if (not line or 
                line.endswith('Learn about the various triggers for') or
                line.startswith('Internal Candidates') or
                line.startswith('ATS - Training Guidance') or
                re.match(r'^[A-Z][a-z\s-]+[A-Z][a-z\s-]+$', line) or  # Title case patterns
                re.match(r'^\[?\d+\]?\s*$', line) or  # Just numbers/references
                len(line) < 10):  # Very short lines (likely metadata)
                continue
                
            # Clean up reference numbers and brackets
            line = re.sub(r'\s*\[\d+\]\s*', ' ', line)
            line = re.sub(r'\s+', ' ', line)  # Multiple spaces to single
            
            if line and len(line) > 15:  # Only keep substantial lines
                cleaned_lines.append(line)
        
        return ' '.join(cleaned_lines).strip()
    
    def _clean_llm_response(self, response: str) -> str:
        """Clean up the LLM response to remove any remaining artifacts"""
        import re
        
        # Remove any remaining confidence scores or metadata
        response = re.sub(r'\d+%\s*confidence', '', response)
        response = re.sub(r'confidence\s*[:=]\s*\d+%?', '', response, flags=re.IGNORECASE)
        
        # Remove document titles that may have leaked through
        response = re.sub(r'Internal Candidates.*?\.\.\.', '', response)
        response = re.sub(r'ATS - Training Guidance.*?\.\.\.', '', response)
        
        # Remove standalone reference numbers or brackets
        response = re.sub(r'\n\s*\[\d+\]\s*\n', '\n', response)
        response = re.sub(r'^\s*\[\d+\]\s*', '', response, flags=re.MULTILINE)
        
        # Clean up excessive whitespace
        response = re.sub(r'\n\s*\n\s*\n', '\n\n', response)  # Max 2 consecutive newlines
        response = re.sub(r'[ \t]+', ' ', response)  # Multiple spaces to single
        
        # Remove any trailing/leading metadata artifacts
        lines = response.split('\n')
        cleaned_lines = []
        
        for line in lines:
            line = line.strip()
            # Skip obviously broken metadata lines
            if (line and 
                not re.match(r'^[A-Z][a-z\s-]+[A-Z][a-z\s-]+$', line) and  # Title patterns
                not re.match(r'^\d+%.*confidence', line) and  # Confidence lines
                len(line) > 3):  # Very short fragments
                cleaned_lines.append(line)
        
        return '\n'.join(cleaned_lines).strip()
    
    def _enhance_citations(self, response: str, sources: List[Dict]) -> str:
        """Enhance response with numbered citations and image references"""
        if not sources:
            return response
        
        # First, handle numbered citations [1], [2], [3] format
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
        
        # Second, handle image references ![description](image_id)
        enhanced_response = self._convert_image_references(enhanced_response, sources)
        
        return enhanced_response
    
    def _convert_image_references(self, response: str, sources: List[Dict]) -> str:
        """Convert image references to actual image tags with URLs"""
        import re
        
        # Pattern to match ![description](image_id)
        image_pattern = r'!\[([^\]]*)\]\(([^)]+)\)'
        
        def replace_image(match):
            description = match.group(1)
            image_id = match.group(2)
            
            print(f"🖼️ DEBUG: Converting image reference: {image_id} ({description})")
            
            # Parse image_id to find the actual image
            # Format: screenshot_0_1 or image_2_0
            try:
                parts = image_id.split('_')
                if len(parts) >= 3:
                    image_type = parts[0]  # 'screenshot' or 'image'
                    source_index = int(parts[1])
                    image_index = int(parts[2])
                    
                    print(f"🖼️ DEBUG: Parsed {image_id} -> type:{image_type}, source:{source_index}, index:{image_index}")
                    
                    if 0 <= source_index < len(sources):
                        source = sources[source_index]
                        metadata = source.get('metadata', {})
                        visual_content = metadata.get('visual_content', {})
                        
                        image_data = None
                        if image_type == 'screenshot':
                            screenshots = visual_content.get('screenshots', [])
                            if 0 <= image_index < len(screenshots):
                                image_data = screenshots[image_index]
                                print(f"✅ DEBUG: Found screenshot data")
                        else:  # 'image'
                            images = visual_content.get('images', [])
                            if 0 <= image_index < len(images):
                                image_data = images[image_index]
                                print(f"✅ DEBUG: Found image data")
                        
                        if image_data:
                            stored_url = image_data.get('stored_url', '')
                            alt_text = image_data.get('alt_text', description)
                            
                            if stored_url:
                                print(f"✅ DEBUG: Converting to img tag: {stored_url}")
                                
                                # Convert MinIO internal URL to public proxy URL
                                if 'minio:9000/rag-documents/' in stored_url:
                                    # Extract the path after /rag-documents/
                                    path_start = stored_url.find('/rag-documents/') + len('/rag-documents/')
                                    # Remove query parameters if present
                                    path_end = stored_url.find('?') if '?' in stored_url else len(stored_url)
                                    object_path = stored_url[path_start:path_end]
                                    
                                    # Convert to full core-api proxy URL (not relative)
                                    # Format: http://localhost:8001/api/images/{organization_slug}/{domain}/{year}/{month}/{image_path}
                                    public_url = f"http://localhost:8001/api/images/{object_path}"
                                    print(f"🔄 DEBUG: Converted MinIO URL to full proxy: {public_url}")
                                else:
                                    # Use original URL if not a MinIO URL
                                    public_url = stored_url
                                
                                # Return HTML img tag with proper attributes
                                return f'<img src="{public_url}" alt="{alt_text}" class="guide-image" style="max-width: 100%; height: auto; margin: 10px 0;" />'
                            else:
                                print(f"❌ DEBUG: No stored URL for {image_id}")
                        else:
                            print(f"❌ DEBUG: No image data found for {image_id}")
                    else:
                        print(f"❌ DEBUG: Source index {source_index} out of range")
                else:
                    print(f"❌ DEBUG: Invalid image_id format: {image_id}")
                
            except (ValueError, IndexError, KeyError) as e:
                print(f"❌ DEBUG: Error parsing {image_id}: {e}")
            
            # Return original if parsing fails or image not found
            print(f"⚠️ DEBUG: Returning original reference for {image_id}")
            return match.group(0)
        
        converted_response = re.sub(image_pattern, replace_image, response)
        
        # Count successful conversions
        original_count = len(re.findall(image_pattern, response))
        remaining_count = len(re.findall(image_pattern, converted_response))
        converted_count = original_count - remaining_count
        
        print(f"🖼️ DEBUG: Image conversion complete: {converted_count}/{original_count} images converted")
        
        return converted_response
    
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
    
    def _extract_image_references(self, sources: List[Dict], query: str = "") -> str:
        """Extract image references using semantic search on image descriptions"""
        image_refs = []
        
        print(f"🔍 DEBUG LLM: Extracting image references from {len(sources)} sources for query: '{query}'")
        
        if not query.strip():
            # No query context, return first few images
            all_images = self._collect_all_images(sources)
            prioritized_images = all_images[:3]
            print(f"🔍 DEBUG LLM: No query context, using first {len(prioritized_images)} images")
        else:
            # Use semantic search on image descriptions
            prioritized_images = self._semantic_image_search(sources, query)
            print(f"🔍 DEBUG LLM: Semantic search selected {len(prioritized_images)} images for query: '{query}'")
        
        # Generate image references for the LLM
        for img in prioritized_images:
            img_id = img['image_id']
            
            # Use description for instruction
            if img.get('enhanced_description'):
                description = img['enhanced_description']
                # Create short, relevant instruction
                short_desc = description[:80] + "..." if len(description) > 80 else description
                instruction = f"![{short_desc}]({img_id})"
            else:
                # Fallback to alt_text
                alt_text = img.get('alt_text', f'Image {img.get("image_index", "")}')
                instruction = f"![{alt_text}]({img_id})"
            
            image_refs.append(instruction)
            print(f"📸 DEBUG LLM: Added image reference: {instruction[:100]}...")
        
        final_image_context = "IMAGE REFERENCES:\n" + "\n".join(image_refs) if image_refs else ""
        
        if final_image_context:
            print(f"🔍 DEBUG LLM: Final image context length: {len(final_image_context)}")
        else:
            print(f"⚠️ DEBUG LLM: No images selected for query: '{query}'")
        
        return final_image_context
    
    def _collect_all_images(self, sources: List[Dict]) -> List[Dict]:
        """Collect all images from sources with metadata"""
        all_images = []
        
        for i, source in enumerate(sources):
            metadata = source.get('metadata', {})
            visual_content = metadata.get('visual_content', {})
            
            if visual_content:
                screenshots = visual_content.get('screenshots', [])
                images = visual_content.get('images', [])
                
                # Add screenshots
                for j, screenshot in enumerate(screenshots):
                    screenshot_with_context = screenshot.copy()
                    screenshot_with_context.update({
                        'source_index': i,
                        'image_index': j,
                        'image_type': 'screenshot',
                        'image_id': f"screenshot_{i}_{j}"
                    })
                    all_images.append(screenshot_with_context)
                
                # Add regular images
                for j, image in enumerate(images):
                    image_with_context = image.copy()
                    image_with_context.update({
                        'source_index': i,
                        'image_index': j,
                        'image_type': 'image',
                        'image_id': f"image_{i}_{j}"
                    })
                    all_images.append(image_with_context)
        
        return all_images
    
    def _semantic_image_search(self, sources: List[Dict], query: str, top_k: int = 3) -> List[Dict]:
        """Use semantic search to find most relevant images for the query using pre-computed embeddings"""
        all_images = self._collect_all_images(sources)
        
        if not all_images:
            print(f"❌ DEBUG: No images found in sources")
            return []
        
        # Try to get embeddings model for query embedding
        try:
            from main import embeddings_model
            if not embeddings_model:
                print(f"⚠️ DEBUG: No embeddings model available, using first {top_k} images")
                return all_images[:top_k]
        except:
            print(f"⚠️ DEBUG: Could not access embeddings model, using first {top_k} images")
            return all_images[:top_k]
        
        try:
            # Check if any images have pre-computed embeddings
            images_with_embeddings = []
            images_without_embeddings = []
            
            for img in all_images:
                if img.get('enhanced_description'):
                    # Try to find pre-computed embedding for this image description
                    pre_computed_embedding = self._get_image_description_embedding(img.get('enhanced_description'))
                    if pre_computed_embedding:
                        img['pre_computed_embedding'] = pre_computed_embedding
                        images_with_embeddings.append(img)
                        print(f"✅ DEBUG: Found pre-computed embedding for image: {img.get('enhanced_description', '')[:50]}...")
                    else:
                        images_without_embeddings.append(img)
                        print(f"⚠️ DEBUG: No pre-computed embedding found for: {img.get('enhanced_description', '')[:50]}...")
                else:
                    images_without_embeddings.append(img)
            
            # If we have pre-computed embeddings, use them for efficient search
            if images_with_embeddings:
                return self._search_with_precomputed_embeddings(query, images_with_embeddings, top_k)
            
            # Fallback: real-time embedding (less efficient but still works)
            print(f"⚠️ DEBUG: No pre-computed embeddings found, falling back to real-time embedding")
            return self._search_with_realtime_embedding(query, images_without_embeddings, top_k)
            
        except Exception as e:
            print(f"❌ DEBUG: Semantic search failed: {e}")
            # Fallback to first few images
            return all_images[:top_k]
    
    def _get_image_description_embedding(self, description: str) -> Optional[List[float]]:
        """Get pre-computed embedding for image description from database"""
        try:
            from dependencies import get_db
            from sqlalchemy import text
            import numpy as np
            
            db = next(get_db())
            
            # Look up pre-computed embedding by description text
            result = db.execute(
                text("""
                    SELECT embedding 
                    FROM embeddings 
                    WHERE source_type = 'image_description' 
                    AND content_text = :description
                    LIMIT 1
                """),
                {"description": description}
            ).fetchone()
            
            if result and result.embedding:
                # PostgreSQL vector column returns list, but ensure it's properly typed
                embedding = result.embedding
                
                # Convert to numpy array and then back to list to ensure proper float types
                if isinstance(embedding, (list, tuple)):
                    # Convert to float array to ensure proper numerical types
                    embedding_array = np.array(embedding, dtype=np.float32)
                    return embedding_array.tolist()
                elif isinstance(embedding, str):
                    # Handle case where it might be returned as string representation
                    try:
                        import json
                        embedding_list = json.loads(embedding)
                        embedding_array = np.array(embedding_list, dtype=np.float32)
                        return embedding_array.tolist()
                    except:
                        print(f"❌ DEBUG: Could not parse embedding string: {embedding[:50]}...")
                        return None
                else:
                    print(f"❌ DEBUG: Unexpected embedding type: {type(embedding)}")
                    return None
            
            return None
            
        except Exception as e:
            print(f"❌ DEBUG: Failed to get pre-computed embedding: {e}")
            return None
    
    def _search_with_precomputed_embeddings(self, query: str, images_with_embeddings: List[Dict], top_k: int) -> List[Dict]:
        """Efficient search using pre-computed embeddings"""
        try:
            from main import embeddings_model
            import numpy as np
            
            # Embed query once
            query_embedding = embeddings_model.encode([query])[0]
            print(f"🔍 DEBUG: Query embedding shape: {query_embedding.shape}, dtype: {query_embedding.dtype}")
            
            # Calculate similarities using pre-computed embeddings
            similarities = []
            for i, img in enumerate(images_with_embeddings):
                try:
                    # Ensure pre-computed embedding is properly typed
                    pre_computed_embedding = np.array(img['pre_computed_embedding'], dtype=np.float32)
                    print(f"🔍 DEBUG: Image {i} embedding shape: {pre_computed_embedding.shape}, dtype: {pre_computed_embedding.dtype}")
                    
                    # Ensure query embedding is also float32 for compatibility
                    query_embedding_typed = np.array(query_embedding, dtype=np.float32)
                    
                    # Calculate cosine similarity
                    similarity = np.dot(query_embedding_typed, pre_computed_embedding) / (
                        np.linalg.norm(query_embedding_typed) * np.linalg.norm(pre_computed_embedding)
                    )
                    similarities.append(float(similarity))  # Ensure it's a Python float
                    
                    description = img.get('enhanced_description', 'No description')[:50]
                    print(f"🔍 DEBUG: Similarity {i}: {similarity:.3f} for '{description}...'")
                    
                except Exception as e:
                    print(f"❌ DEBUG: Failed to calculate similarity for image {i}: {e}")
                    similarities.append(0.0)  # Add zero similarity for failed calculations
            
            if not similarities:
                print(f"❌ DEBUG: No valid similarities calculated")
                return images_with_embeddings[:top_k]
            
            # Get top-k most similar images
            top_indices = np.argsort(similarities)[-top_k:][::-1]  # Descending order
            
            selected_images = []
            for idx in top_indices:
                if similarities[idx] > 0.1:  # Minimum similarity threshold
                    img = images_with_embeddings[idx]
                    img['similarity_score'] = similarities[idx]
                    selected_images.append(img)
                    description = img.get('enhanced_description', 'No description')
                    print(f"✅ DEBUG: Selected image (pre-computed, similarity: {similarities[idx]:.3f}): {description[:80]}...")
                else:
                    description = images_with_embeddings[idx].get('enhanced_description', 'No description')
                    print(f"⚠️ DEBUG: Image similarity too low ({similarities[idx]:.3f}): {description[:80]}...")
            
            if not selected_images:
                print(f"⚠️ DEBUG: No images met similarity threshold, returning top 1 anyway")
                if images_with_embeddings:
                    best_idx = top_indices[0]
                    img = images_with_embeddings[best_idx]
                    img['similarity_score'] = similarities[best_idx]
                    selected_images.append(img)
            
            return selected_images
            
        except Exception as e:
            print(f"❌ DEBUG: Pre-computed embedding search failed: {e}")
            import traceback
            print(f"❌ DEBUG: Full traceback: {traceback.format_exc()}")
            return images_with_embeddings[:top_k]  # Fallback
    
    def _search_with_realtime_embedding(self, query: str, images: List[Dict], top_k: int) -> List[Dict]:
        """Fallback: real-time embedding search (original approach)"""
        from main import embeddings_model
        
        # Collect image descriptions for semantic search
        image_descriptions = []
        valid_images = []
        
        for img in images:
            # Get the best available description
            description = ""
            
            if img.get('enhanced_description'):
                description = img['enhanced_description']
            elif img.get('alt_text'):
                description = img['alt_text']
            else:
                # Skip images without descriptions
                continue
            
            image_descriptions.append(description)
            valid_images.append(img)
            
            print(f"📝 DEBUG: Image description: {description[:100]}...")
        
        if not image_descriptions:
            print(f"❌ DEBUG: No images with descriptions found")
            return []
        
        try:
            # Embed query and image descriptions
            query_embedding = embeddings_model.encode([query])[0]
            description_embeddings = embeddings_model.encode(image_descriptions)
            
            # Calculate similarities
            import numpy as np
            similarities = []
            for desc_embedding in description_embeddings:
                similarity = np.dot(query_embedding, desc_embedding) / (
                    np.linalg.norm(query_embedding) * np.linalg.norm(desc_embedding)
                )
                similarities.append(similarity)
            
            # Get top-k most similar images
            top_indices = np.argsort(similarities)[-top_k:][::-1]  # Descending order
            
            selected_images = []
            for idx in top_indices:
                if similarities[idx] > 0.1:  # Minimum similarity threshold
                    img = valid_images[idx]
                    img['similarity_score'] = similarities[idx]
                    selected_images.append(img)
                    print(f"✅ DEBUG: Selected image (real-time, similarity: {similarities[idx]:.3f}): {image_descriptions[idx][:80]}...")
                else:
                    print(f"⚠️ DEBUG: Image similarity too low ({similarities[idx]:.3f}): {image_descriptions[idx][:80]}...")
            
            return selected_images
            
        except Exception as e:
            print(f"❌ DEBUG: Real-time embedding search failed: {e}")
            # Fallback to first few images
            return valid_images[:top_k]
    
    def _initialize_vision(self):
        """Initialize vision analyzer if available"""
        try:
            from vision_analyzer import get_vision_analyzer
            self.vision_analyzer = get_vision_analyzer()
            if self.vision_analyzer.available:
                logger.info("✅ Vision analyzer initialized")
            else:
                logger.info("⚠️ Vision analyzer not available (no vision model)")
        except Exception as e:
            logger.error(f"❌ Failed to initialize vision analyzer: {e}")
            self.vision_analyzer = None

# Global instance
llm_service = LLMService()

def get_llm_service() -> LLMService:
    """Get the global LLM service instance"""
    return llm_service 
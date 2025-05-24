"""
Embedding Service for generating text embeddings
Supports both OpenAI and Ollama providers with fallback
"""

import hashlib
import asyncio
from typing import List, Optional
import numpy as np
import httpx
import openai
from openai import AsyncOpenAI

from config import Settings


class EmbeddingService:
    """Service for generating text embeddings"""
    
    def __init__(self, settings: Settings):
        self.settings = settings
        self.provider = settings.EMBEDDING_PROVIDER
        self.openai_client = None
        self.ollama_client = None
        
    async def initialize(self):
        """Initialize the embedding service"""
        if self.provider == "openai" or self.settings.OPENAI_API_KEY != "your_openai_key_here":
            self.openai_client = AsyncOpenAI(api_key=self.settings.OPENAI_API_KEY)
        
        # Initialize HTTP client for Ollama
        self.ollama_client = httpx.AsyncClient(timeout=30.0)
        
    async def generate_embedding(self, text: str) -> np.ndarray:
        """
        Generate embedding for a single text
        """
        try:
            if self.provider == "openai" and self.openai_client:
                return await self._generate_openai_embedding(text)
            elif self.provider == "ollama":
                return await self._generate_ollama_embedding(text)
            else:
                # Fallback to mock embedding for development
                return self._generate_mock_embedding(text)
        except Exception as e:
            print(f"Error generating embedding with {self.provider}: {e}")
            # Try fallback provider
            if self.provider == "openai":
                try:
                    return await self._generate_ollama_embedding(text)
                except:
                    return self._generate_mock_embedding(text)
            else:
                try:
                    if self.openai_client:
                        return await self._generate_openai_embedding(text)
                    else:
                        return self._generate_mock_embedding(text)
                except:
                    return self._generate_mock_embedding(text)
    
    async def generate_embeddings_batch(self, texts: List[str]) -> List[np.ndarray]:
        """
        Generate embeddings for multiple texts in batch
        """
        if self.provider == "openai" and self.openai_client:
            return await self._generate_openai_embeddings_batch(texts)
        else:
            # Process individually for Ollama or mock
            tasks = [self.generate_embedding(text) for text in texts]
            return await asyncio.gather(*tasks)
    
    async def _generate_openai_embedding(self, text: str) -> np.ndarray:
        """Generate embedding using OpenAI API"""
        response = await self.openai_client.embeddings.create(
            model=self.settings.EMBEDDING_MODEL,
            input=text,
            encoding_format="float"
        )
        return np.array(response.data[0].embedding, dtype=np.float32)
    
    async def _generate_openai_embeddings_batch(self, texts: List[str]) -> List[np.ndarray]:
        """Generate embeddings in batch using OpenAI API"""
        response = await self.openai_client.embeddings.create(
            model=self.settings.EMBEDDING_MODEL,
            input=texts,
            encoding_format="float"
        )
        return [np.array(data.embedding, dtype=np.float32) for data in response.data]
    
    async def _generate_ollama_embedding(self, text: str) -> np.ndarray:
        """Generate embedding using Ollama API"""
        try:
            response = await self.ollama_client.post(
                f"{self.settings.OLLAMA_BASE_URL}/api/embeddings",
                json={
                    "model": "nomic-embed-text",  # Default Ollama embedding model
                    "prompt": text
                }
            )
            response.raise_for_status()
            data = response.json()
            return np.array(data["embedding"], dtype=np.float32)
        except Exception as e:
            print(f"Ollama embedding error: {e}")
            # Fallback to mock embedding
            return self._generate_mock_embedding(text)
    
    def _generate_mock_embedding(self, text: str) -> np.ndarray:
        """
        Generate mock embedding for development/testing
        Creates a deterministic embedding based on text hash
        """
        # Use text hash to create deterministic but varied embedding
        text_hash = hashlib.md5(text.encode()).hexdigest()
        
        # Convert hash to numeric seed
        seed = int(text_hash[:8], 16)
        np.random.seed(seed)
        
        # Generate random embedding that's deterministic for the same text
        embedding = np.random.normal(0, 1, self.settings.VECTOR_DIMENSION).astype(np.float32)
        
        # Normalize to unit vector
        norm = np.linalg.norm(embedding)
        if norm > 0:
            embedding = embedding / norm
        
        return embedding
    
    def get_text_hash(self, text: str) -> str:
        """Generate hash for text content"""
        return hashlib.sha256(text.encode()).hexdigest()
    
    async def health_check(self) -> dict:
        """Check health of embedding service"""
        status = {
            "provider": self.provider,
            "openai_available": self.openai_client is not None,
            "ollama_available": False
        }
        
        # Test Ollama availability
        try:
            response = await self.ollama_client.get(f"{self.settings.OLLAMA_BASE_URL}/api/tags")
            status["ollama_available"] = response.status_code == 200
        except:
            pass
        
        return status
    
    async def close(self):
        """Close HTTP clients"""
        if self.ollama_client:
            await self.ollama_client.aclose() 
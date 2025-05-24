"""
Vector Store for indexing and searching embeddings
Supports FAISS as the primary implementation with pgvector fallback
"""

import os
import pickle
import asyncio
from pathlib import Path
from typing import List, Dict, Any, Optional
import numpy as np
import faiss

from config import Settings


class VectorStore:
    """Vector store for embedding indexing and search"""
    
    def __init__(self, settings: Settings):
        self.settings = settings
        self.index = None
        self.id_to_index = {}  # Maps embedding IDs to FAISS indices
        self.index_to_id = {}  # Maps FAISS indices to embedding IDs
        self.metadata_store = {}  # Stores metadata for each embedding
        self.index_path = Path(settings.FAISS_INDEX_PATH)
        self.next_index = 0
        
    async def initialize(self):
        """Initialize the vector store"""
        # Create index directory
        self.index_path.mkdir(parents=True, exist_ok=True)
        
        # Initialize or load FAISS index
        await self._load_or_create_index()
        
    async def _load_or_create_index(self):
        """Load existing index or create new one"""
        index_file = self.index_path / "faiss.index"
        metadata_file = self.index_path / "metadata.pkl"
        mappings_file = self.index_path / "mappings.pkl"
        
        if index_file.exists() and metadata_file.exists() and mappings_file.exists():
            try:
                # Load existing index
                self.index = faiss.read_index(str(index_file))
                
                with open(metadata_file, 'rb') as f:
                    self.metadata_store = pickle.load(f)
                
                with open(mappings_file, 'rb') as f:
                    data = pickle.load(f)
                    self.id_to_index = data['id_to_index']
                    self.index_to_id = data['index_to_id']
                    self.next_index = data['next_index']
                
                print(f"Loaded existing FAISS index with {self.index.ntotal} vectors")
            except Exception as e:
                print(f"Error loading index: {e}, creating new one")
                await self._create_new_index()
        else:
            await self._create_new_index()
    
    async def _create_new_index(self):
        """Create a new FAISS index"""
        # Create FAISS index (Inner Product for normalized vectors)
        self.index = faiss.IndexFlatIP(self.settings.VECTOR_DIMENSION)
        self.id_to_index = {}
        self.index_to_id = {}
        self.metadata_store = {}
        self.next_index = 0
        print(f"Created new FAISS index with dimension {self.settings.VECTOR_DIMENSION}")
    
    async def add_embedding(self, embedding_id: str, embedding: np.ndarray, metadata: Dict[str, Any] = None):
        """Add an embedding to the vector store"""
        try:
            # Ensure embedding is normalized
            if np.linalg.norm(embedding) > 0:
                embedding = embedding / np.linalg.norm(embedding)
            
            # Add to FAISS index
            embedding_2d = embedding.reshape(1, -1).astype(np.float32)
            self.index.add(embedding_2d)
            
            # Update mappings
            faiss_index = self.next_index
            self.id_to_index[embedding_id] = faiss_index
            self.index_to_id[faiss_index] = embedding_id
            self.metadata_store[embedding_id] = metadata or {}
            self.next_index += 1
            
            # Save index periodically
            if self.next_index % 100 == 0:
                await self._save_index()
            
        except Exception as e:
            print(f"Error adding embedding {embedding_id}: {e}")
            raise
    
    async def search(
        self, 
        query_embedding: np.ndarray, 
        top_k: int = 10, 
        similarity_threshold: float = 0.7
    ) -> List[Dict[str, Any]]:
        """Search for similar embeddings"""
        try:
            if self.index.ntotal == 0:
                return []
            
            # Ensure query embedding is normalized
            if np.linalg.norm(query_embedding) > 0:
                query_embedding = query_embedding / np.linalg.norm(query_embedding)
            
            # Search FAISS index
            query_2d = query_embedding.reshape(1, -1).astype(np.float32)
            similarities, indices = self.index.search(query_2d, min(top_k, self.index.ntotal))
            
            # Convert results
            results = []
            for i, (similarity, faiss_idx) in enumerate(zip(similarities[0], indices[0])):
                if faiss_idx == -1:  # FAISS returns -1 for invalid indices
                    continue
                
                # Convert cosine similarity from inner product (both vectors are normalized)
                similarity_score = float(similarity)
                
                if similarity_score >= similarity_threshold:
                    embedding_id = self.index_to_id.get(faiss_idx)
                    if embedding_id:
                        results.append({
                            "id": embedding_id,
                            "similarity": similarity_score,
                            "metadata": self.metadata_store.get(embedding_id, {})
                        })
            
            return results
            
        except Exception as e:
            print(f"Error searching embeddings: {e}")
            return []
    
    async def delete_embedding(self, embedding_id: str):
        """Delete an embedding from the vector store"""
        # Note: FAISS doesn't support efficient deletion
        # For production, consider using a more sophisticated approach
        # For now, we'll just remove from mappings and metadata
        faiss_index = self.id_to_index.pop(embedding_id, None)
        if faiss_index is not None:
            self.index_to_id.pop(faiss_index, None)
            self.metadata_store.pop(embedding_id, None)
        
        # TODO: Implement proper index rebuilding for production
    
    async def _save_index(self):
        """Save the FAISS index and metadata to disk"""
        try:
            index_file = self.index_path / "faiss.index"
            metadata_file = self.index_path / "metadata.pkl"
            mappings_file = self.index_path / "mappings.pkl"
            
            # Save FAISS index
            faiss.write_index(self.index, str(index_file))
            
            # Save metadata
            with open(metadata_file, 'wb') as f:
                pickle.dump(self.metadata_store, f)
            
            # Save mappings
            with open(mappings_file, 'wb') as f:
                pickle.dump({
                    'id_to_index': self.id_to_index,
                    'index_to_id': self.index_to_id,
                    'next_index': self.next_index
                }, f)
            
        except Exception as e:
            print(f"Error saving index: {e}")
    
    async def health_check(self) -> str:
        """Check health of vector store"""
        try:
            if self.index is None:
                return "not_initialized"
            
            vector_count = self.index.ntotal
            return f"healthy_{vector_count}_vectors"
            
        except Exception as e:
            return f"error_{str(e)}"
    
    async def get_stats(self) -> Dict[str, Any]:
        """Get statistics about the vector store"""
        return {
            "total_vectors": self.index.ntotal if self.index else 0,
            "vector_dimension": self.settings.VECTOR_DIMENSION,
            "index_type": "FAISS_IndexFlatIP",
            "next_index": self.next_index,
            "metadata_count": len(self.metadata_store)
        }
    
    async def close(self):
        """Close and save the vector store"""
        await self._save_index()
        print("Vector store closed and saved") 
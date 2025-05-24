"""
Multi-Domain Vector Store
Manages separate FAISS indices for each domain
"""

import os
import pickle
import asyncio
from pathlib import Path
from typing import List, Dict, Any, Optional, Tuple
import numpy as np
import faiss
from sqlalchemy.orm import Session

from config import Settings
from domains.domain_config import DomainConfigManager, DomainSettings


class DomainVectorStore:
    """Vector store for a specific domain"""
    
    def __init__(self, domain_config: DomainSettings, settings: Settings):
        self.domain_config = domain_config
        self.settings = settings
        self.index = None
        self.id_to_index = {}  # Maps embedding IDs to FAISS indices
        self.index_to_id = {}  # Maps FAISS indices to embedding IDs
        self.metadata_store = {}  # Stores metadata for each embedding
        self.index_path = Path(domain_config.vector_index_path)
        self.index_path.mkdir(parents=True, exist_ok=True)

    async def initialize(self):
        """Initialize the domain-specific FAISS index"""
        try:
            await self.load_index()
            print(f"Loaded existing FAISS index for domain '{self.domain_config.domain_name}' with {self.get_vector_count()} vectors")
        except Exception as e:
            print(f"Creating new FAISS index for domain '{self.domain_config.domain_name}': {e}")
            await self.create_index()

    async def create_index(self):
        """Create a new FAISS index for the domain"""
        # Create FAISS index (using IndexFlatIP for inner product similarity)
        self.index = faiss.IndexFlatIP(self.settings.VECTOR_DIMENSION)
        
        # Clear mappings
        self.id_to_index.clear()
        self.index_to_id.clear()
        self.metadata_store.clear()
        
        # Save the new index
        await self.save_index()

    async def load_index(self):
        """Load FAISS index from disk"""
        index_file = self.index_path / "faiss.index"
        mappings_file = self.index_path / "mappings.pkl"
        metadata_file = self.index_path / "metadata.pkl"
        
        if not all(f.exists() for f in [index_file, mappings_file, metadata_file]):
            raise FileNotFoundError("Index files not found")
        
        # Load FAISS index
        self.index = faiss.read_index(str(index_file))
        
        # Load mappings and metadata
        with open(mappings_file, 'rb') as f:
            data = pickle.load(f)
            self.id_to_index = data['id_to_index']
            self.index_to_id = data['index_to_id']
        
        with open(metadata_file, 'rb') as f:
            self.metadata_store = pickle.load(f)

    async def save_index(self):
        """Save FAISS index to disk"""
        index_file = self.index_path / "faiss.index"
        mappings_file = self.index_path / "mappings.pkl"
        metadata_file = self.index_path / "metadata.pkl"
        
        # Save FAISS index
        faiss.write_index(self.index, str(index_file))
        
        # Save mappings
        with open(mappings_file, 'wb') as f:
            pickle.dump({
                'id_to_index': self.id_to_index,
                'index_to_id': self.index_to_id
            }, f)
        
        # Save metadata
        with open(metadata_file, 'wb') as f:
            pickle.dump(self.metadata_store, f)

    async def add_embedding(self, embedding_id: str, vector: np.ndarray, metadata: Dict[str, Any]):
        """Add a vector to the domain index"""
        if embedding_id in self.id_to_index:
            return  # Already exists
        
        # Normalize vector for cosine similarity
        vector = vector / np.linalg.norm(vector)
        vector = vector.reshape(1, -1).astype(np.float32)
        
        # Add to FAISS index
        faiss_index = self.index.ntotal
        self.index.add(vector)
        
        # Update mappings
        self.id_to_index[embedding_id] = faiss_index
        self.index_to_id[faiss_index] = embedding_id
        self.metadata_store[embedding_id] = metadata
        
        # Save periodically (every 10 additions)
        if len(self.id_to_index) % 10 == 0:
            await self.save_index()

    async def search(self, query_vector: np.ndarray, top_k: int = 10) -> List[Dict[str, Any]]:
        """Search for similar vectors in the domain"""
        if self.index.ntotal == 0:
            return []
        
        # Normalize query vector
        query_vector = query_vector / np.linalg.norm(query_vector)
        query_vector = query_vector.reshape(1, -1).astype(np.float32)
        
        # Search in FAISS index
        k = min(top_k, self.index.ntotal)
        similarities, indices = self.index.search(query_vector, k)
        
        results = []
        for i, (similarity, faiss_idx) in enumerate(zip(similarities[0], indices[0])):
            if faiss_idx == -1:  # No more results
                break
            
            if similarity < self.domain_config.similarity_threshold:
                continue
            
            embedding_id = self.index_to_id.get(faiss_idx)
            if embedding_id:
                metadata = self.metadata_store.get(embedding_id, {})
                results.append({
                    "id": embedding_id,
                    "similarity": float(similarity),
                    "metadata": metadata,
                    "domain": self.domain_config.domain_name
                })
        
        return results

    async def remove_embedding(self, embedding_id: str) -> bool:
        """Remove an embedding from the domain index"""
        if embedding_id not in self.id_to_index:
            return False
        
        # Note: FAISS doesn't support efficient removal
        # In production, consider rebuilding index periodically
        faiss_index = self.id_to_index[embedding_id]
        
        # Remove from mappings
        del self.id_to_index[embedding_id]
        del self.index_to_id[faiss_index]
        del self.metadata_store[embedding_id]
        
        return True

    def get_vector_count(self) -> int:
        """Get number of vectors in the domain index"""
        return self.index.ntotal if self.index else 0

    def get_stats(self) -> Dict[str, Any]:
        """Get domain index statistics"""
        return {
            "domain": self.domain_config.domain_name,
            "vector_count": self.get_vector_count(),
            "dimension": self.settings.VECTOR_DIMENSION,
            "similarity_threshold": self.domain_config.similarity_threshold,
            "index_path": str(self.index_path),
            "embedding_model": self.domain_config.embedding_model
        }


class MultiDomainVectorStore:
    """Manages multiple domain-specific vector stores"""
    
    def __init__(self, settings: Settings):
        self.settings = settings
        self.domain_stores: Dict[str, DomainVectorStore] = {}
        self.domain_config_manager: Optional[DomainConfigManager] = None

    async def initialize(self, db_session: Session):
        """Initialize all domain vector stores"""
        self.domain_config_manager = DomainConfigManager(db_session)
        
        # Get all active domains
        domains = self.domain_config_manager.get_all_active_domains()
        
        # Initialize vector store for each domain
        for domain_config in domains:
            domain_store = DomainVectorStore(domain_config, self.settings)
            await domain_store.initialize()
            self.domain_stores[domain_config.domain_name] = domain_store
        
        print(f"Initialized {len(self.domain_stores)} domain vector stores")

    async def get_domain_store(self, domain_name: str) -> Optional[DomainVectorStore]:
        """Get vector store for a specific domain"""
        return self.domain_stores.get(domain_name)

    async def add_embedding(self, domain: str, embedding_id: str, 
                           vector: np.ndarray, metadata: Dict[str, Any]):
        """Add embedding to specific domain"""
        domain_store = await self.get_domain_store(domain)
        if domain_store:
            await domain_store.add_embedding(embedding_id, vector, metadata)
        else:
            raise ValueError(f"Domain '{domain}' not found")

    async def search_domain(self, domain: str, query_vector: np.ndarray, 
                           top_k: int = 10) -> List[Dict[str, Any]]:
        """Search within a specific domain"""
        domain_store = await self.get_domain_store(domain)
        if domain_store:
            return await domain_store.search(query_vector, top_k)
        else:
            return []

    async def search_multiple_domains(self, domains: List[str], query_vector: np.ndarray, 
                                    top_k: int = 10) -> List[Dict[str, Any]]:
        """Search across multiple domains and merge results"""
        all_results = []
        
        # Search each domain
        for domain in domains:
            domain_results = await self.search_domain(domain, query_vector, top_k)
            all_results.extend(domain_results)
        
        # Sort by similarity and take top_k
        all_results.sort(key=lambda x: x["similarity"], reverse=True)
        return all_results[:top_k]

    async def search_all_accessible_domains(self, user_domains: List[str], 
                                          query_vector: np.ndarray, 
                                          top_k: int = 10) -> List[Dict[str, Any]]:
        """Search across all domains user has access to"""
        accessible_domains = [d for d in user_domains if d in self.domain_stores]
        return await self.search_multiple_domains(accessible_domains, query_vector, top_k)

    async def remove_embedding(self, domain: str, embedding_id: str) -> bool:
        """Remove embedding from specific domain"""
        domain_store = await self.get_domain_store(domain)
        if domain_store:
            return await domain_store.remove_embedding(embedding_id)
        return False

    async def get_domain_stats(self, domain: str) -> Optional[Dict[str, Any]]:
        """Get statistics for a specific domain"""
        domain_store = await self.get_domain_store(domain)
        if domain_store:
            return domain_store.get_stats()
        return None

    async def get_all_stats(self) -> Dict[str, Any]:
        """Get statistics for all domains"""
        stats = {
            "total_domains": len(self.domain_stores),
            "domains": {}
        }
        
        total_vectors = 0
        for domain_name, domain_store in self.domain_stores.items():
            domain_stats = domain_store.get_stats()
            stats["domains"][domain_name] = domain_stats
            total_vectors += domain_stats["vector_count"]
        
        stats["total_vectors"] = total_vectors
        return stats

    async def refresh_domains(self, db_session: Session):
        """Refresh domain configurations and add new domains"""
        if not self.domain_config_manager:
            self.domain_config_manager = DomainConfigManager(db_session)
        
        # Get current active domains
        domains = self.domain_config_manager.get_all_active_domains()
        
        # Add new domains
        for domain_config in domains:
            if domain_config.domain_name not in self.domain_stores:
                domain_store = DomainVectorStore(domain_config, self.settings)
                await domain_store.initialize()
                self.domain_stores[domain_config.domain_name] = domain_store
                print(f"Added new domain vector store: {domain_config.domain_name}")

    async def save_all_indices(self):
        """Save all domain indices to disk"""
        for domain_store in self.domain_stores.values():
            await domain_store.save_index()
        print("Saved all domain indices") 
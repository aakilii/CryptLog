"""
Embedding Service for Oracle 26AI Open-Source Implementation.

Phase 1: Foundation - Singleton embedding model management with
sentence-transformers for local, free, high-quality embeddings.
"""

import logging
from typing import Any, Dict, List, Optional, Union
from dataclasses import dataclass
import threading
import numpy as np

logger = logging.getLogger(__name__)


@dataclass
class EmbeddingResult:
    """Result of an embedding operation."""
    text: str
    embedding: List[float]
    model: str
    dimension: int


@dataclass
class ModelInfo:
    """Information about the loaded embedding model."""
    name: str
    dimension: int
    device: str
    max_seq_length: int
    loaded: bool


class EmbeddingService:
    """
    Singleton embedding service using sentence-transformers.
    
    Features:
    - Lazy loading (loads model on first use)
    - Thread-safe singleton pattern
    - GPU/CPU auto-detection
    - Batch processing for efficiency
    - Caching layer (optional, via ChromaDB)
    """
    
    _instance: Optional['EmbeddingService'] = None
    _lock = threading.Lock()
    
    def __new__(cls, *args, **kwargs):
        if cls._instance is None:
            with cls._lock:
                if cls._instance is None:
                    cls._instance = super().__new__(cls)
                    cls._instance._initialized = False
        return cls._instance
    
    def __init__(
        self,
        model_name: str = "all-MiniLM-L6-v2",
        device: str = "auto",
        batch_size: int = 32
    ):
        if self._initialized:
            return
            
        self.model_name = model_name
        self.device = device
        self.batch_size = batch_size
        
        self._model = None
        self._dimension: Optional[int] = None
        self._actual_device: Optional[str] = None
        self._initialized = True
        
        logger.info(f"EmbeddingService initialized: model={model_name}, device={device}")
    
    def _load_model(self) -> None:
        """Lazy load the embedding model."""
        if self._model is not None:
            return
            
        try:
            from sentence_transformers import SentenceTransformer
            import torch
            
            # Determine device
            if self.device == "auto":
                self._actual_device = "cuda" if torch.cuda.is_available() else "cpu"
            else:
                self._actual_device = self.device
            
            logger.info(f"Loading embedding model '{self.model_name}' on {self._actual_device}...")
            
            self._model = SentenceTransformer(
                self.model_name,
                device=self._actual_device
            )
            
            # Get embedding dimension from model
            self._dimension = self._model.get_sentence_embedding_dimension()
            
            logger.info(f"Embedding model loaded: dim={self._dimension}, device={self._actual_device}")
            
        except ImportError:
            logger.error("sentence-transformers not installed. Run: pip install sentence-transformers")
            raise RuntimeError("sentence-transformers package required for embedding service")
        except Exception as e:
            logger.error(f"Failed to load embedding model: {e}")
            raise
    
    def embed_text(self, text: str) -> List[float]:
        """
        Embed a single text string.
        
        Args:
            text: Text to embed
            
        Returns:
            Embedding vector as list of floats
        """
        self._load_model()
        
        if not text or not text.strip():
            logger.warning("Empty text provided for embedding, returning zeros")
            return [0.0] * (self._dimension or 384)
        
        model = self._model
        if model is None:
            raise RuntimeError("Embedding model failed to initialize")

        embedding = model.encode(
            text,
            convert_to_numpy=True,
            normalize_embeddings=True
        )
        
        return embedding.tolist()

    # Backward-compatible alias used by existing services.
    def embed(self, text: str) -> List[float]:
        return self.embed_text(text)
    
    def embed_batch(self, texts: List[str]) -> List[List[float]]:
        """
        Embed multiple texts efficiently using batching.
        
        Args:
            texts: List of texts to embed
            
        Returns:
            List of embedding vectors
        """
        self._load_model()
        
        if not texts:
            return []
        
        # Filter empty texts but track indices
        valid_indices = []
        valid_texts = []
        for i, text in enumerate(texts):
            if text and text.strip():
                valid_indices.append(i)
                valid_texts.append(text)
        
        if not valid_texts:
            return [[0.0] * (self._dimension or 384) for _ in texts]

        model = self._model
        if model is None:
            raise RuntimeError("Embedding model failed to initialize")
        
        # Batch encode
        embeddings = model.encode(
            valid_texts,
            batch_size=self.batch_size,
            convert_to_numpy=True,
            normalize_embeddings=True,
            show_progress_bar=len(valid_texts) > 100
        )
        
        # Reconstruct full result list
        result = [[0.0] * (self._dimension or 384) for _ in texts]
        for orig_idx, embedding in zip(valid_indices, embeddings):
            result[orig_idx] = embedding.tolist()
        
        return result

    # Backward-compatible alias used by existing services.
    def embed_many(self, texts: List[str]) -> List[List[float]]:
        return self.embed_batch(texts)
    
    def embed_with_metadata(self, text: str) -> EmbeddingResult:
        """
        Embed text and return with metadata.
        
        Args:
            text: Text to embed
            
        Returns:
            EmbeddingResult with embedding and metadata
        """
        embedding = self.embed_text(text)
        
        return EmbeddingResult(
            text=text,
            embedding=embedding,
            model=self.model_name,
            dimension=self._dimension or len(embedding)
        )
    
    def get_model_info(self) -> ModelInfo:
        """Get information about the loaded model."""
        self._load_model()
        
        return ModelInfo(
            name=self.model_name,
            dimension=self._dimension or 384,
            device=self._actual_device or "unknown",
            max_seq_length=self._model.max_seq_length if self._model else 256,
            loaded=self._model is not None
        )
    
    def similarity(self, text1: str, text2: str) -> float:
        """
        Calculate cosine similarity between two texts.
        
        Args:
            text1: First text
            text2: Second text
            
        Returns:
            Similarity score between -1 and 1
        """
        emb1 = np.array(self.embed_text(text1))
        emb2 = np.array(self.embed_text(text2))
        
        # Cosine similarity (embeddings are normalized)
        return float(np.dot(emb1, emb2))
    
    def batch_similarity(self, query: str, candidates: List[str]) -> List[float]:
        """
        Calculate similarity of query against multiple candidates.
        
        Args:
            query: Query text
            candidates: List of candidate texts
            
        Returns:
            List of similarity scores
        """
        if not candidates:
            return []
        
        query_emb = np.array(self.embed_text(query))
        candidate_embs = np.array(self.embed_batch(candidates))
        
        # Batch cosine similarity
        similarities = np.dot(candidate_embs, query_emb)
        
        return similarities.tolist()
    
    @property
    def dimension(self) -> int:
        """Get embedding dimension."""
        if self._dimension is None:
            self._load_model()
        return self._dimension or 384
    
    @property
    def is_loaded(self) -> bool:
        """Check if model is loaded."""
        return self._model is not None


# Module-level singleton accessor
_service: Optional[EmbeddingService] = None


def get_embedding_service(
    model_name: Optional[str] = None,
    device: Optional[str] = None,
    batch_size: Optional[int] = None
) -> EmbeddingService:
    """
    Get the embedding service singleton.
    
    On first call, initializes with provided or default config.
    Subsequent calls return the same instance.
    
    Args:
        model_name: Optional model name override
        device: Optional device override
        batch_size: Optional batch size override
        
    Returns:
        EmbeddingService singleton instance
    """
    global _service
    
    if _service is None:
        from operation_room.config import settings
        
        _service = EmbeddingService(
            model_name=model_name or settings.EMBEDDING_MODEL,
            device=device or settings.EMBEDDING_DEVICE,
            batch_size=batch_size or settings.EMBEDDING_BATCH_SIZE
        )
    
    return _service


def embed_text(text: str) -> List[float]:
    """Convenience function to embed a single text."""
    return get_embedding_service().embed_text(text)


def embed_batch(texts: List[str]) -> List[List[float]]:
    """Convenience function to embed multiple texts."""
    return get_embedding_service().embed_batch(texts)

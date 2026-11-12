"""
Vector Store Service for Oracle 26AI Open-Source Implementation.

Phase 1: Foundation - ChromaDB wrapper with collection management
for evidence embeddings, session memory, and retrieval.
"""

import logging
import hashlib
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple, Union
from dataclasses import dataclass, field
from enum import Enum

logger = logging.getLogger(__name__)


class CollectionType(str, Enum):
    """Types of vector collections for different data isolation."""
    EVIDENCE = "evidence"           # Per-case evidence embeddings
    SESSION = "session"             # Per-session conversation memory
    HYPOTHESIS = "hypothesis"       # Per-case hypothesis embeddings
    TEMPLATES = "templates"         # Global procedural templates
    CALIBRATION = "calibration"     # Global calibration data
    # Learning collections
    REPORT_STRUCTURES = "learned_report_structures"    # Full report hierarchies
    SECTION_PATTERNS = "learned_section_patterns"      # Individual section styles
    CHART_PATTERNS = "learned_chart_patterns"          # Chart usage patterns
    TERMINOLOGY = "learned_terminology"                 # Domain terminology
    LEARNING_FEEDBACK = "learning_feedback"             # User feedback entries


@dataclass
class VectorDocument:
    """Document to store in vector database."""
    id: str
    content: str
    embedding: Optional[List[float]] = None
    metadata: Dict[str, Any] = field(default_factory=dict)
    
    def __post_init__(self):
        if not self.id:
            # Generate ID from content hash
            self.id = hashlib.sha256(self.content.encode()).hexdigest()[:16]


@dataclass
class SearchResult:
    """Result from vector similarity search."""
    id: str
    content: str
    score: float
    metadata: Dict[str, Any] = field(default_factory=dict)


@dataclass
class CollectionStats:
    """Statistics for a collection."""
    name: str
    count: int
    embedding_dimension: int


class VectorStore:
    """
    ChromaDB wrapper for vector storage and retrieval.
    
    Features:
    - Per-case isolation via collection namespacing
    - Global collections for shared data (templates, calibration)
    - Hybrid search support (semantic + metadata filtering)
    - Automatic embedding generation via EmbeddingService
    """
    
    def __init__(
        self,
        persist_directory: str = "./data/vectordb",
        embedding_dimension: int = 384
    ):
        """
        Initialize vector store.
        
        Args:
            persist_directory: Directory for ChromaDB persistence
            embedding_dimension: Dimension of embeddings (must match model)
        """
        self.persist_directory = Path(persist_directory)
        self.persist_directory.mkdir(parents=True, exist_ok=True)
        
        self.embedding_dimension = embedding_dimension
        
        self._client = None
        self._collections: Dict[str, Any] = {}
        self._embedding_service = None
        
        logger.info(f"VectorStore initialized: path={persist_directory}, dim={embedding_dimension}")
    
    def _get_client(self):
        """Lazy initialize ChromaDB client."""
        if self._client is None:
            try:
                import chromadb
                from chromadb.config import Settings
                
                self._client = chromadb.PersistentClient(
                    path=str(self.persist_directory),
                    settings=Settings(
                        anonymized_telemetry=False,
                        allow_reset=True
                    )
                )
                
                logger.info(f"ChromaDB client initialized: {self.persist_directory}")
                
            except ImportError:
                logger.error("chromadb not installed. Run: pip install chromadb")
                raise RuntimeError("chromadb package required for vector store")
        
        return self._client
    
    def _get_embedding_service(self):
        """Get embedding service singleton."""
        if self._embedding_service is None:
            from operation_room.services.embedding_service import get_embedding_service
            self._embedding_service = get_embedding_service()
        return self._embedding_service
    
    def _collection_name(self, collection_type: CollectionType, case_id: Optional[str] = None) -> str:
        """
        Generate collection name with optional case isolation.
        
        Per-case collections: f"{case_id}_{collection_type}"
        Global collections: f"global_{collection_type}"
        """
        if collection_type in (CollectionType.TEMPLATES, CollectionType.CALIBRATION):
            # Global collections - shared across all cases
            return f"global_{collection_type.value}"
        elif case_id:
            # Per-case isolated collections
            return f"{case_id}_{collection_type.value}"
        else:
            raise ValueError(f"case_id required for collection type: {collection_type}")
    
    def _get_collection(self, collection_type: CollectionType, case_id: Optional[str] = None):
        """Get or create a collection."""
        name = self._collection_name(collection_type, case_id)
        
        if name not in self._collections:
            client = self._get_client()
            
            try:
                self._collections[name] = client.get_or_create_collection(
                    name=name,
                    metadata={
                        "collection_type": collection_type.value,
                        "case_id": case_id or "global",
                        "created_at": datetime.utcnow().isoformat(),
                        "dimension": self.embedding_dimension
                    }
                )
                logger.debug(f"Collection ready: {name}")
            except Exception as e:
                logger.error(f"Failed to create collection {name}: {e}")
                raise
        
        return self._collections[name]
    
    def add_document(
        self,
        collection_type: CollectionType,
        content: str,
        metadata: Dict[str, Any] = None,
        doc_id: Optional[str] = None,
        case_id: Optional[str] = None,
        embedding: Optional[List[float]] = None
    ) -> str:
        """
        Add a document to a collection.
        
        Args:
            collection_type: Type of collection
            content: Text content
            metadata: Optional metadata dict
            doc_id: Optional document ID (auto-generated if not provided)
            case_id: Case ID for per-case collections
            embedding: Pre-computed embedding (computed if not provided)
            
        Returns:
            Document ID
        """
        collection = self._get_collection(collection_type, case_id)
        
        # Generate ID if not provided
        if not doc_id:
            doc_id = hashlib.sha256(f"{content}{datetime.utcnow().isoformat()}".encode()).hexdigest()[:16]
        
        # Generate embedding if not provided
        if embedding is None:
            embedding = self._get_embedding_service().embed_text(content)
        
        # Prepare metadata
        meta = metadata or {}
        meta["added_at"] = datetime.utcnow().isoformat()
        meta["content_hash"] = hashlib.sha256(content.encode()).hexdigest()[:16]
        
        try:
            collection.add(
                ids=[doc_id],
                embeddings=[embedding],
                documents=[content],
                metadatas=[meta]
            )
            
            logger.debug(f"Added document {doc_id} to {collection.name}")
            return doc_id
            
        except Exception as e:
            logger.error(f"Failed to add document: {e}")
            raise
    
    def add_documents(
        self,
        collection_type: CollectionType,
        documents: List[VectorDocument],
        case_id: Optional[str] = None
    ) -> List[str]:
        """
        Add multiple documents to a collection.
        
        Args:
            collection_type: Type of collection
            documents: List of VectorDocument objects
            case_id: Case ID for per-case collections
            
        Returns:
            List of document IDs
        """
        if not documents:
            return []
        
        collection = self._get_collection(collection_type, case_id)
        
        # Extract fields
        ids = [doc.id for doc in documents]
        contents = [doc.content for doc in documents]
        metadatas = [doc.metadata for doc in documents]
        
        # Generate embeddings for documents without them
        embeddings = []
        texts_to_embed = []
        embed_indices = []
        
        for i, doc in enumerate(documents):
            if doc.embedding:
                embeddings.append(doc.embedding)
            else:
                embeddings.append(None)
                texts_to_embed.append(doc.content)
                embed_indices.append(i)
        
        if texts_to_embed:
            batch_embeddings = self._get_embedding_service().embed_batch(texts_to_embed)
            for idx, emb in zip(embed_indices, batch_embeddings):
                embeddings[idx] = emb
        
        # Add timestamps
        for meta in metadatas:
            meta["added_at"] = datetime.utcnow().isoformat()
        
        try:
            collection.add(
                ids=ids,
                embeddings=embeddings,
                documents=contents,
                metadatas=metadatas
            )
            
            logger.info(f"Added {len(documents)} documents to {collection.name}")
            return ids
            
        except Exception as e:
            logger.error(f"Failed to add documents: {e}")
            raise
    
    def search(
        self,
        collection_type: CollectionType,
        query: str,
        case_id: Optional[str] = None,
        n_results: int = 10,
        where: Optional[Dict[str, Any]] = None,
        where_document: Optional[Dict[str, Any]] = None,
        query_embedding: Optional[List[float]] = None
    ) -> List[SearchResult]:
        """
        Search for similar documents.
        
        Args:
            collection_type: Type of collection to search
            query: Query text
            case_id: Case ID for per-case collections
            n_results: Maximum number of results
            where: Optional metadata filter (ChromaDB syntax)
            where_document: Optional document content filter
            query_embedding: Pre-computed query embedding
            
        Returns:
            List of SearchResult objects sorted by similarity
        """
        collection = self._get_collection(collection_type, case_id)
        
        # Generate query embedding if not provided
        if query_embedding is None:
            query_embedding = self._get_embedding_service().embed_text(query)
        
        try:
            results = collection.query(
                query_embeddings=[query_embedding],
                n_results=n_results,
                where=where,
                where_document=where_document,
                include=["documents", "metadatas", "distances"]
            )
            
            # Convert to SearchResult objects
            search_results = []
            
            if results and results.get("ids") and results["ids"][0]:
                for i in range(len(results["ids"][0])):
                    # ChromaDB returns distances, convert to similarity scores
                    distance = results["distances"][0][i] if results.get("distances") else 0
                    # L2 distance to cosine similarity approximation
                    similarity = 1.0 / (1.0 + distance)
                    
                    search_results.append(SearchResult(
                        id=results["ids"][0][i],
                        content=results["documents"][0][i] if results.get("documents") else "",
                        score=similarity,
                        metadata=results["metadatas"][0][i] if results.get("metadatas") else {}
                    ))
            
            logger.debug(f"Search returned {len(search_results)} results from {collection.name}")
            return search_results
            
        except Exception as e:
            logger.error(f"Search failed: {e}")
            return []
    
    def delete(
        self,
        collection_type: CollectionType,
        doc_ids: List[str],
        case_id: Optional[str] = None
    ) -> int:
        """
        Delete documents by ID.
        
        Args:
            collection_type: Type of collection
            doc_ids: List of document IDs to delete
            case_id: Case ID for per-case collections
            
        Returns:
            Number of documents deleted
        """
        collection = self._get_collection(collection_type, case_id)
        
        try:
            collection.delete(ids=doc_ids)
            logger.info(f"Deleted {len(doc_ids)} documents from {collection.name}")
            return len(doc_ids)
        except Exception as e:
            logger.error(f"Delete failed: {e}")
            return 0
    
    def update_metadata(
        self,
        collection_type: CollectionType,
        doc_id: str,
        metadata: Dict[str, Any],
        case_id: Optional[str] = None
    ) -> bool:
        """
        Update document metadata.
        
        Args:
            collection_type: Type of collection
            doc_id: Document ID
            metadata: New metadata to merge
            case_id: Case ID for per-case collections
            
        Returns:
            True if successful
        """
        collection = self._get_collection(collection_type, case_id)
        
        try:
            # Get existing document
            existing = collection.get(ids=[doc_id], include=["metadatas"])
            
            if not existing or not existing.get("ids"):
                logger.warning(f"Document {doc_id} not found")
                return False
            
            # Merge metadata
            current_meta = existing["metadatas"][0] if existing.get("metadatas") else {}
            merged_meta = {**current_meta, **metadata, "updated_at": datetime.utcnow().isoformat()}
            
            # Update
            collection.update(ids=[doc_id], metadatas=[merged_meta])
            
            logger.debug(f"Updated metadata for {doc_id}")
            return True
            
        except Exception as e:
            logger.error(f"Update failed: {e}")
            return False
    
    def get_collection_stats(
        self,
        collection_type: CollectionType,
        case_id: Optional[str] = None
    ) -> CollectionStats:
        """Get statistics for a collection."""
        collection = self._get_collection(collection_type, case_id)
        
        return CollectionStats(
            name=collection.name,
            count=collection.count(),
            embedding_dimension=self.embedding_dimension
        )
    
    def list_collections(self, case_id: Optional[str] = None) -> List[str]:
        """
        List available collections.
        
        Args:
            case_id: If provided, filter to collections for this case
            
        Returns:
            List of collection names
        """
        client = self._get_client()
        all_collections = client.list_collections()
        
        names = [c.name for c in all_collections]
        
        if case_id:
            # Filter to case-specific and global collections
            names = [n for n in names if n.startswith(f"{case_id}_") or n.startswith("global_")]
        
        return names
    
    def delete_collection(
        self,
        collection_type: CollectionType,
        case_id: Optional[str] = None
    ) -> bool:
        """
        Delete an entire collection.
        
        Args:
            collection_type: Type of collection
            case_id: Case ID for per-case collections
            
        Returns:
            True if successful
        """
        name = self._collection_name(collection_type, case_id)
        
        try:
            client = self._get_client()
            client.delete_collection(name)
            
            if name in self._collections:
                del self._collections[name]
            
            logger.info(f"Deleted collection: {name}")
            return True
            
        except Exception as e:
            logger.error(f"Failed to delete collection {name}: {e}")
            return False
    
    def reset(self) -> None:
        """Reset all collections (use with caution)."""
        client = self._get_client()
        client.reset()
        self._collections = {}
        logger.warning("Vector store reset - all collections deleted")
    
    # ───────────────────────────────────────────────────────────────────────────
    # STRING-BASED COLLECTION ACCESS (for learning service)
    # ───────────────────────────────────────────────────────────────────────────
    
    def _get_collection_by_name(self, collection_name: str):
        """Get or create a collection by string name."""
        if collection_name not in self._collections:
            client = self._get_client()
            try:
                self._collections[collection_name] = client.get_or_create_collection(
                    name=collection_name,
                    metadata={
                        "created_at": datetime.utcnow().isoformat(),
                        "dimension": self.embedding_dimension
                    }
                )
            except Exception as e:
                logger.error(f"Failed to create collection {collection_name}: {e}")
                raise
        return self._collections[collection_name]
    
    def add_documents(
        self,
        collection_name: str,
        documents: List[VectorDocument]
    ) -> List[str]:
        """
        Add documents to a named collection.
        
        This is a convenience method that accepts collection name as string,
        used by the learning service.
        """
        if not documents:
            return []
        
        collection = self._get_collection_by_name(collection_name)
        
        ids = [doc.id for doc in documents]
        contents = [doc.content for doc in documents]
        metadatas = [doc.metadata for doc in documents]
        
        # Handle embeddings
        embeddings = []
        texts_to_embed = []
        embed_indices = []
        
        for i, doc in enumerate(documents):
            if doc.embedding:
                embeddings.append(doc.embedding)
            else:
                embeddings.append(None)
                texts_to_embed.append(doc.content)
                embed_indices.append(i)
        
        if texts_to_embed:
            batch_embeddings = self._get_embedding_service().embed_batch(texts_to_embed)
            for idx, emb in zip(embed_indices, batch_embeddings):
                embeddings[idx] = emb
        
        for meta in metadatas:
            meta["added_at"] = datetime.utcnow().isoformat()
        
        try:
            collection.add(
                ids=ids,
                embeddings=embeddings,
                documents=contents,
                metadatas=metadatas
            )
            logger.info(f"Added {len(documents)} documents to {collection_name}")
            return ids
        except Exception as e:
            logger.error(f"Failed to add documents to {collection_name}: {e}")
            raise
    
    def search(
        self,
        collection_name: str,
        query: str,
        n_results: int = 10,
        where: Optional[Dict[str, Any]] = None
    ) -> List[SearchResult]:
        """
        Search a named collection.
        
        This is a convenience method that accepts collection name as string.
        """
        collection = self._get_collection_by_name(collection_name)
        
        query_embedding = self._get_embedding_service().embed_text(query)
        
        try:
            results = collection.query(
                query_embeddings=[query_embedding],
                n_results=n_results,
                where=where,
                include=["documents", "metadatas", "distances"]
            )
            
            search_results = []
            if results and results.get("ids") and results["ids"][0]:
                for i in range(len(results["ids"][0])):
                    distance = results["distances"][0][i] if results.get("distances") else 0
                    similarity = 1.0 / (1.0 + distance)
                    
                    search_results.append(SearchResult(
                        id=results["ids"][0][i],
                        content=results["documents"][0][i] if results.get("documents") else "",
                        score=similarity,
                        metadata=results["metadatas"][0][i] if results.get("metadatas") else {}
                    ))
            
            return search_results
        except Exception as e:
            logger.error(f"Search failed in {collection_name}: {e}")
            return []
    
    def count(self, collection_name: str) -> int:
        """Get document count in a named collection."""
        try:
            collection = self._get_collection_by_name(collection_name)
            return collection.count()
        except Exception:
            return 0
    
    def get_all(
        self,
        collection_name: str,
        where: Optional[Dict[str, Any]] = None,
        limit: int = 100
    ) -> List[SearchResult]:
        """Get all documents from a named collection."""
        try:
            collection = self._get_collection_by_name(collection_name)
            results = collection.get(
                where=where,
                limit=limit,
                include=["documents", "metadatas"]
            )
            
            items = []
            if results and results.get("ids"):
                for i in range(len(results["ids"])):
                    items.append(SearchResult(
                        id=results["ids"][i],
                        content=results["documents"][i] if results.get("documents") else "",
                        score=1.0,
                        metadata=results["metadatas"][i] if results.get("metadatas") else {}
                    ))
            return items
        except Exception as e:
            logger.error(f"get_all failed for {collection_name}: {e}")
            return []


# Module-level singleton
_store: Optional[VectorStore] = None


def get_vector_store(
    persist_directory: str = None,
    embedding_dimension: int = None
) -> VectorStore:
    """
    Get the vector store singleton.
    
    Args:
        persist_directory: Optional path override
        embedding_dimension: Optional dimension override
        
    Returns:
        VectorStore singleton instance
    """
    global _store
    
    if _store is None:
        from operation_room.config import settings
        
        _store = VectorStore(
            persist_directory=persist_directory or settings.VECTOR_STORE_PATH,
            embedding_dimension=embedding_dimension or settings.EMBEDDING_DIMENSION
        )
    
    return _store


def add_evidence_embedding(
    case_id: str,
    content: str,
    metadata: Dict[str, Any] = None,
    doc_id: Optional[str] = None
) -> str:
    """Convenience function to add evidence to vector store."""
    return get_vector_store().add_document(
        collection_type=CollectionType.EVIDENCE,
        content=content,
        metadata=metadata,
        doc_id=doc_id,
        case_id=case_id
    )


def search_evidence(
    case_id: str,
    query: str,
    n_results: int = 10,
    where: Optional[Dict[str, Any]] = None
) -> List[SearchResult]:
    """Convenience function to search evidence."""
    return get_vector_store().search(
        collection_type=CollectionType.EVIDENCE,
        query=query,
        case_id=case_id,
        n_results=n_results,
        where=where
    )

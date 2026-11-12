"""
Hybrid Retriever Service - Oracle 26AI Phase 7.

High-quality retrieval combining:
- Semantic search (dense vectors)
- BM25 keyword search (sparse)
- Cross-encoder reranking
- Reciprocal Rank Fusion (RRF)
"""

import logging
from datetime import datetime
from typing import Any, Dict, List, Optional, Tuple
from dataclasses import dataclass, field
from enum import Enum

from operation_room.services.vector_store import get_vector_store, CollectionType, SearchResult
from operation_room.services.embedding_service import get_embedding_service

logger = logging.getLogger(__name__)


class RetrievalStrategy(str, Enum):
    """Retrieval strategy options."""
    SEMANTIC_ONLY = "semantic"
    KEYWORD_ONLY = "keyword"
    HYBRID_LINEAR = "hybrid_linear"
    HYBRID_RRF = "hybrid_rrf"


@dataclass
class RetrievalResult:
    """Result from hybrid retrieval."""
    doc_id: str
    content: str
    score: float
    semantic_score: float = 0.0
    keyword_score: float = 0.0
    rerank_score: Optional[float] = None
    metadata: Dict[str, Any] = field(default_factory=dict)
    retrieval_method: str = "hybrid"


@dataclass
class RetrievalMetrics:
    """Metrics for retrieval quality."""
    total_retrieved: int
    semantic_candidates: int
    keyword_candidates: int
    reranked: bool
    avg_score: float
    retrieval_time_ms: float


class BM25Index:
    """
    BM25 keyword index for efficient text retrieval.
    """
    
    def __init__(self):
        self._corpus: List[List[str]] = []
        self._doc_ids: List[str] = []
        self._bm25 = None
        self._initialized = False
    
    def build_index(self, documents: List[Tuple[str, str]]) -> None:
        """
        Build BM25 index from documents.
        
        Args:
            documents: List of (doc_id, content) tuples
        """
        try:
            from rank_bm25 import BM25Okapi
            
            self._doc_ids = [doc_id for doc_id, _ in documents]
            self._corpus = [content.lower().split() for _, content in documents]
            
            self._bm25 = BM25Okapi(self._corpus)
            self._initialized = True
            
            logger.info(f"BM25 index built with {len(self._doc_ids)} documents")
            
        except ImportError:
            logger.warning("rank_bm25 not installed, BM25 search disabled")
            self._initialized = False
    
    def search(self, query: str, n_results: int = 10) -> List[Tuple[str, float]]:
        """
        Search using BM25.
        
        Args:
            query: Search query
            n_results: Maximum results
            
        Returns:
            List of (doc_id, score) tuples
        """
        if not self._initialized or self._bm25 is None:
            return []
        
        query_tokens = query.lower().split()
        scores = self._bm25.get_scores(query_tokens)
        
        # Normalize scores
        max_score = max(scores) if scores.any() else 1.0
        if max_score > 0:
            normalized_scores = scores / max_score
        else:
            normalized_scores = scores
        
        # Get top results
        results = [
            (self._doc_ids[i], float(normalized_scores[i]))
            for i in range(len(scores))
            if normalized_scores[i] > 0
        ]
        
        results.sort(key=lambda x: x[1], reverse=True)
        return results[:n_results]


class CrossEncoderReranker:
    """
    Cross-encoder for reranking search results.
    
    Uses a cross-encoder model to compute more accurate
    relevance scores between query and documents.
    """
    
    def __init__(self, model_name: str = "cross-encoder/ms-marco-MiniLM-L-6-v2"):
        self.model_name = model_name
        self._model = None
        self._initialized = False
    
    def _load_model(self) -> bool:
        """Lazy load the cross-encoder model."""
        if self._model is not None:
            return True
        
        try:
            from sentence_transformers import CrossEncoder
            
            logger.info(f"Loading cross-encoder: {self.model_name}")
            self._model = CrossEncoder(self.model_name)
            self._initialized = True
            
            return True
            
        except ImportError:
            logger.warning("sentence-transformers not installed, reranking disabled")
            return False
        except Exception as e:
            logger.error(f"Failed to load cross-encoder: {e}")
            return False
    
    def rerank(
        self,
        query: str,
        documents: List[Tuple[str, str, float]],
        top_k: int = 10
    ) -> List[Tuple[str, str, float]]:
        """
        Rerank documents using cross-encoder.
        
        Args:
            query: Search query
            documents: List of (doc_id, content, initial_score) tuples
            top_k: Number of top results to return
            
        Returns:
            Reranked list of (doc_id, content, rerank_score) tuples
        """
        if not self._load_model():
            return documents[:top_k]
        
        if not documents:
            return []
        
        # Prepare pairs for cross-encoder
        pairs = [(query, content) for _, content, _ in documents]
        
        # Get rerank scores
        scores = self._model.predict(pairs)
        
        # Combine with document info
        reranked = [
            (documents[i][0], documents[i][1], float(scores[i]))
            for i in range(len(documents))
        ]
        
        # Sort by rerank score
        reranked.sort(key=lambda x: x[2], reverse=True)
        
        return reranked[:top_k]
    
    @property
    def is_available(self) -> bool:
        """Check if reranker is available."""
        return self._load_model()


class HybridRetriever:
    """
    Hybrid retrieval combining semantic and keyword search.
    
    Features:
    - Semantic search via embeddings
    - BM25 keyword search
    - Reciprocal Rank Fusion (RRF) for score combination
    - Optional cross-encoder reranking
    """
    
    # RRF constant (higher = more emphasis on top ranks)
    RRF_K = 60
    
    def __init__(
        self,
        case_id: str,
        collection_type: CollectionType = CollectionType.EVIDENCE,
        enable_reranking: bool = True
    ):
        self.case_id = case_id
        self.collection_type = collection_type
        self.enable_reranking = enable_reranking
        
        self._vector_store = get_vector_store()
        self._embedding_service = get_embedding_service()
        self._bm25_index = BM25Index()
        self._reranker = CrossEncoderReranker() if enable_reranking else None
        
        self._corpus_loaded = False
    
    def _ensure_corpus(self) -> None:
        """Load corpus for BM25 if not already loaded."""
        if self._corpus_loaded:
            return
        
        try:
            from operation_room.database import open_vault
            
            # Load documents from database
            conn = open_vault(self.case_id)
            try:
                if self.collection_type == CollectionType.EVIDENCE:
                    rows = conn.execute("""
                        SELECT evidence_id, content
                        FROM evidence_registry
                        WHERE case_id = ?
                    """, [self.case_id]).fetchall()
                else:
                    # For other collections, we might not have SQL backup
                    rows = []
                
                if rows:
                    self._bm25_index.build_index([(r[0], r[1]) for r in rows])
                    self._corpus_loaded = True
                    
            finally:
                conn.close()
                
        except Exception as e:
            logger.warning(f"Failed to load BM25 corpus: {e}")
    
    def retrieve(
        self,
        query: str,
        n_results: int = 10,
        strategy: RetrievalStrategy = RetrievalStrategy.HYBRID_RRF,
        semantic_weight: float = 0.7,
        keyword_weight: float = 0.3,
        rerank: bool = True,
        where: Optional[Dict[str, Any]] = None
    ) -> Tuple[List[RetrievalResult], RetrievalMetrics]:
        """
        Retrieve relevant documents using hybrid search.
        
        Args:
            query: Search query
            n_results: Maximum number of results
            strategy: Retrieval strategy to use
            semantic_weight: Weight for semantic scores (linear fusion)
            keyword_weight: Weight for keyword scores (linear fusion)
            rerank: Whether to apply reranking
            where: Optional metadata filter
            
        Returns:
            Tuple of (results, metrics)
        """
        import time
        start_time = time.time()
        
        # Fetch more candidates for fusion
        candidates_multiplier = 3 if strategy in (RetrievalStrategy.HYBRID_LINEAR, RetrievalStrategy.HYBRID_RRF) else 1
        n_candidates = n_results * candidates_multiplier
        
        # Semantic search
        semantic_results = []
        if strategy != RetrievalStrategy.KEYWORD_ONLY:
            semantic_results = self._semantic_search(query, n_candidates, where)
        
        # Keyword search
        keyword_results = []
        if strategy != RetrievalStrategy.SEMANTIC_ONLY:
            self._ensure_corpus()
            keyword_results = self._bm25_index.search(query, n_candidates)
        
        # Combine results based on strategy
        if strategy == RetrievalStrategy.SEMANTIC_ONLY:
            combined = self._semantic_only(semantic_results)
        elif strategy == RetrievalStrategy.KEYWORD_ONLY:
            combined = self._keyword_only(keyword_results)
        elif strategy == RetrievalStrategy.HYBRID_LINEAR:
            combined = self._linear_fusion(
                semantic_results, keyword_results,
                semantic_weight, keyword_weight
            )
        else:  # HYBRID_RRF
            combined = self._rrf_fusion(semantic_results, keyword_results)
        
        # Sort by combined score
        combined.sort(key=lambda x: x.score, reverse=True)
        
        # Apply reranking if enabled
        reranked = False
        if rerank and self.enable_reranking and self._reranker:
            combined = self._apply_reranking(query, combined[:n_results * 2])
            reranked = True
        
        # Limit to requested number
        results = combined[:n_results]
        
        # Calculate metrics
        elapsed_ms = (time.time() - start_time) * 1000
        avg_score = sum(r.score for r in results) / len(results) if results else 0.0
        
        metrics = RetrievalMetrics(
            total_retrieved=len(results),
            semantic_candidates=len(semantic_results),
            keyword_candidates=len(keyword_results),
            reranked=reranked,
            avg_score=avg_score,
            retrieval_time_ms=elapsed_ms
        )
        
        return results, metrics
    
    def _semantic_search(
        self,
        query: str,
        n_results: int,
        where: Optional[Dict[str, Any]] = None
    ) -> List[SearchResult]:
        """Perform semantic search."""
        try:
            return self._vector_store.search(
                collection_type=self.collection_type,
                query=query,
                case_id=self.case_id,
                n_results=n_results,
                where=where
            )
        except Exception as e:
            logger.error(f"Semantic search failed: {e}")
            return []
    
    def _semantic_only(self, semantic_results: List[SearchResult]) -> List[RetrievalResult]:
        """Convert semantic results to RetrievalResult."""
        return [
            RetrievalResult(
                doc_id=r.id,
                content=r.content,
                score=r.score,
                semantic_score=r.score,
                metadata=r.metadata,
                retrieval_method="semantic"
            )
            for r in semantic_results
        ]
    
    def _keyword_only(self, keyword_results: List[Tuple[str, float]]) -> List[RetrievalResult]:
        """Convert keyword results to RetrievalResult."""
        results = []
        for doc_id, score in keyword_results:
            # Need to fetch content
            content = self._get_content(doc_id)
            results.append(RetrievalResult(
                doc_id=doc_id,
                content=content,
                score=score,
                keyword_score=score,
                retrieval_method="keyword"
            ))
        return results
    
    def _linear_fusion(
        self,
        semantic_results: List[SearchResult],
        keyword_results: List[Tuple[str, float]],
        semantic_weight: float,
        keyword_weight: float
    ) -> List[RetrievalResult]:
        """Combine results using linear fusion."""
        # Build score maps
        semantic_scores = {r.id: r for r in semantic_results}
        keyword_scores = {doc_id: score for doc_id, score in keyword_results}
        
        # Get all unique doc IDs
        all_ids = set(semantic_scores.keys()) | set(keyword_scores.keys())
        
        results = []
        for doc_id in all_ids:
            sem_score = semantic_scores.get(doc_id)
            kw_score = keyword_scores.get(doc_id, 0.0)
            
            semantic_val = sem_score.score if sem_score else 0.0
            content = sem_score.content if sem_score else self._get_content(doc_id)
            metadata = sem_score.metadata if sem_score else {}
            
            combined_score = (semantic_val * semantic_weight) + (kw_score * keyword_weight)
            
            results.append(RetrievalResult(
                doc_id=doc_id,
                content=content,
                score=combined_score,
                semantic_score=semantic_val,
                keyword_score=kw_score,
                metadata=metadata,
                retrieval_method="hybrid_linear"
            ))
        
        return results
    
    def _rrf_fusion(
        self,
        semantic_results: List[SearchResult],
        keyword_results: List[Tuple[str, float]]
    ) -> List[RetrievalResult]:
        """
        Combine results using Reciprocal Rank Fusion.
        
        RRF score = sum(1 / (k + rank)) for each ranking
        """
        # Build rank maps (1-indexed)
        semantic_ranks = {r.id: i + 1 for i, r in enumerate(semantic_results)}
        keyword_ranks = {doc_id: i + 1 for i, (doc_id, _) in enumerate(keyword_results)}
        
        # Get all unique doc IDs
        all_ids = set(semantic_ranks.keys()) | set(keyword_ranks.keys())
        
        # Calculate RRF scores
        results = []
        for doc_id in all_ids:
            rrf_score = 0.0
            
            if doc_id in semantic_ranks:
                rrf_score += 1.0 / (self.RRF_K + semantic_ranks[doc_id])
            
            if doc_id in keyword_ranks:
                rrf_score += 1.0 / (self.RRF_K + keyword_ranks[doc_id])
            
            # Get content and metadata
            sem_result = next((r for r in semantic_results if r.id == doc_id), None)
            content = sem_result.content if sem_result else self._get_content(doc_id)
            metadata = sem_result.metadata if sem_result else {}
            
            sem_score = sem_result.score if sem_result else 0.0
            kw_score = dict(keyword_results).get(doc_id, 0.0)
            
            results.append(RetrievalResult(
                doc_id=doc_id,
                content=content,
                score=rrf_score,
                semantic_score=sem_score,
                keyword_score=kw_score,
                metadata=metadata,
                retrieval_method="hybrid_rrf"
            ))
        
        return results
    
    def _apply_reranking(
        self,
        query: str,
        results: List[RetrievalResult]
    ) -> List[RetrievalResult]:
        """Apply cross-encoder reranking."""
        if not results or not self._reranker:
            return results
        
        # Prepare for reranking
        docs = [(r.doc_id, r.content, r.score) for r in results]
        
        # Rerank
        reranked = self._reranker.rerank(query, docs, top_k=len(docs))
        
        # Map back to RetrievalResult
        result_map = {r.doc_id: r for r in results}
        
        return [
            RetrievalResult(
                doc_id=doc_id,
                content=content,
                score=rerank_score,
                semantic_score=result_map[doc_id].semantic_score,
                keyword_score=result_map[doc_id].keyword_score,
                rerank_score=rerank_score,
                metadata=result_map[doc_id].metadata,
                retrieval_method=result_map[doc_id].retrieval_method + "_reranked"
            )
            for doc_id, content, rerank_score in reranked
            if doc_id in result_map
        ]
    
    def _get_content(self, doc_id: str) -> str:
        """Get document content by ID."""
        try:
            from operation_room.database import open_vault
            
            conn = open_vault(self.case_id)
            try:
                if self.collection_type == CollectionType.EVIDENCE:
                    row = conn.execute("""
                        SELECT content FROM evidence_registry WHERE evidence_id = ?
                    """, [doc_id]).fetchone()
                    return row[0] if row else ""
            finally:
                conn.close()
        except:
            pass
        return ""


# Factory function
def get_hybrid_retriever(
    case_id: str,
    collection_type: CollectionType = CollectionType.EVIDENCE,
    enable_reranking: bool = True
) -> HybridRetriever:
    """Create a hybrid retriever for a case."""
    return HybridRetriever(case_id, collection_type, enable_reranking)

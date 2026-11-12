"""
Evidence Vault Service - Oracle 26AI Phase 2 Enhancement.

Enhanced evidence management with:
- Vector embeddings for semantic search
- Evidence-claim linking (bidirectional)
- Hybrid search (semantic + keyword)
- Provenance logging
- Evidence validation scoring
"""

import hashlib
import json
import logging
import uuid
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional, Tuple
from dataclasses import dataclass, field

from operation_room.database import open_vault
from operation_room.services.vector_store import (
    get_vector_store, 
    CollectionType, 
    VectorDocument, 
    SearchResult
)
from operation_room.services.embedding_service import get_embedding_service
from operation_room.services.findings_vault import FindingsVault, get_findings_vault

logger = logging.getLogger(__name__)


@dataclass
class EvidenceItem:
    """An evidence item with vector embedding."""
    evidence_id: str
    case_id: str
    content: str
    evidence_type: str  # log, artifact, document, screenshot, etc.
    source: str  # Where it came from
    confidence: float = 0.5
    hash: str = ""
    metadata: Dict[str, Any] = field(default_factory=dict)
    embedding_id: Optional[str] = None
    created_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))


@dataclass
class EvidenceLink:
    """Link between a claim/finding and evidence."""
    link_id: str
    claim_id: str
    evidence_id: str
    link_type: str  # supports, contradicts, related
    confidence: float = 0.5
    created_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    created_by: str = "system"


@dataclass 
class ProvenanceEntry:
    """Audit log entry for evidence operations."""
    entry_id: str
    entity_type: str  # evidence, claim, link
    entity_id: str
    action: str  # create, update, delete, link, validate
    actor: str
    timestamp: datetime
    details: Dict[str, Any] = field(default_factory=dict)


@dataclass
class HybridSearchResult:
    """Result from hybrid search combining semantic and keyword."""
    evidence_id: str
    content: str
    semantic_score: float
    keyword_score: float
    combined_score: float
    metadata: Dict[str, Any] = field(default_factory=dict)


class EvidenceVault:
    """
    Enhanced evidence vault with vector search and linking.
    
    Phase 2 of Oracle 26AI implementation:
    - Store evidence with vector embeddings
    - Link evidence to claims/findings
    - Hybrid search (semantic + BM25 keyword)
    - Full provenance tracking
    """
    
    def __init__(self, case_id: str):
        self.case_id = case_id
        self._findings_vault = get_findings_vault(case_id)
        self._vector_store = get_vector_store()
        self._embedding_service = get_embedding_service()
        self._bm25_index = None  # Lazy loaded
        self._ensure_schema()
    
    def _ensure_schema(self) -> None:
        """Create evidence-related tables."""
        conn = open_vault(self.case_id)
        try:
            # Evidence registry table
            conn.execute("""
                CREATE TABLE IF NOT EXISTS evidence_registry (
                    evidence_id VARCHAR PRIMARY KEY,
                    case_id VARCHAR NOT NULL,
                    content TEXT NOT NULL,
                    evidence_type VARCHAR NOT NULL,
                    source VARCHAR,
                    confidence FLOAT DEFAULT 0.5,
                    content_hash VARCHAR NOT NULL,
                    embedding_id VARCHAR,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    metadata JSON
                )
            """)
            
            # Evidence-claim links
            conn.execute("""
                CREATE TABLE IF NOT EXISTS evidence_links (
                    link_id VARCHAR PRIMARY KEY,
                    claim_id VARCHAR NOT NULL,
                    evidence_id VARCHAR NOT NULL,
                    link_type VARCHAR NOT NULL,
                    confidence FLOAT DEFAULT 0.5,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    created_by VARCHAR DEFAULT 'system',
                    UNIQUE(claim_id, evidence_id)
                )
            """)
            
            # Provenance log
            conn.execute("""
                CREATE TABLE IF NOT EXISTS evidence_provenance (
                    entry_id VARCHAR PRIMARY KEY,
                    entity_type VARCHAR NOT NULL,
                    entity_id VARCHAR NOT NULL,
                    action VARCHAR NOT NULL,
                    actor VARCHAR DEFAULT 'system',
                    timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    details JSON
                )
            """)
            
            # Indexes
            conn.execute("""
                CREATE INDEX IF NOT EXISTS idx_evidence_case 
                ON evidence_registry(case_id)
            """)
            conn.execute("""
                CREATE INDEX IF NOT EXISTS idx_evidence_links_claim 
                ON evidence_links(claim_id)
            """)
            conn.execute("""
                CREATE INDEX IF NOT EXISTS idx_evidence_links_evidence 
                ON evidence_links(evidence_id)
            """)
            conn.execute("""
                CREATE INDEX IF NOT EXISTS idx_provenance_entity 
                ON evidence_provenance(entity_type, entity_id)
            """)
            
        finally:
            conn.close()
    
    def add_evidence(
        self,
        content: str,
        evidence_type: str,
        source: str,
        confidence: float = 0.5,
        metadata: Optional[Dict[str, Any]] = None,
        evidence_id: Optional[str] = None
    ) -> str:
        """
        Add evidence to the vault with vector embedding.
        
        Args:
            content: Evidence content/text
            evidence_type: Type (log, artifact, document, etc.)
            source: Source of evidence
            confidence: Confidence score 0-1
            metadata: Additional metadata
            evidence_id: Optional ID (auto-generated if not provided)
            
        Returns:
            Evidence ID
        """
        if not evidence_id:
            evidence_id = str(uuid.uuid4())[:16]
        
        content_hash = hashlib.sha256(content.encode()).hexdigest()
        meta = metadata or {}
        meta['evidence_type'] = evidence_type
        meta['source'] = source
        meta['confidence'] = confidence
        
        # Add to vector store
        embedding_id = self._vector_store.add_document(
            collection_type=CollectionType.EVIDENCE,
            content=content,
            metadata=meta,
            doc_id=evidence_id,
            case_id=self.case_id
        )
        
        # Add to SQL registry
        conn = open_vault(self.case_id)
        try:
            conn.execute("""
                INSERT INTO evidence_registry (
                    evidence_id, case_id, content, evidence_type, source,
                    confidence, content_hash, embedding_id, metadata, created_at, updated_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, now(), now())
                ON CONFLICT(evidence_id) DO UPDATE SET
                    content = excluded.content,
                    confidence = excluded.confidence,
                    updated_at = now(),
                    metadata = excluded.metadata
            """, [
                evidence_id,
                self.case_id,
                content,
                evidence_type,
                source,
                confidence,
                content_hash,
                embedding_id,
                json.dumps(meta)
            ])
            
            # Log provenance
            self._log_provenance(
                entity_type='evidence',
                entity_id=evidence_id,
                action='create',
                details={'type': evidence_type, 'source': source, 'hash': content_hash[:16]}
            )
            
        finally:
            conn.close()
        
        logger.info(f"Added evidence {evidence_id}: {evidence_type} from {source}")
        return evidence_id
    
    def link_evidence(
        self,
        claim_id: str,
        evidence_id: str,
        link_type: str = "supports",
        confidence: float = 0.5,
        created_by: str = "system"
    ) -> str:
        """
        Link evidence to a claim/finding.
        
        Args:
            claim_id: ID of the claim/finding
            evidence_id: ID of the evidence
            link_type: Type of link (supports, contradicts, related)
            confidence: Link confidence 0-1
            created_by: Who created this link
            
        Returns:
            Link ID
        """
        link_id = f"link_{uuid.uuid4().hex[:12]}"
        
        conn = open_vault(self.case_id)
        try:
            conn.execute("""
                INSERT INTO evidence_links (
                    link_id, claim_id, evidence_id, link_type, confidence, created_by
                ) VALUES (?, ?, ?, ?, ?, ?)
                ON CONFLICT(claim_id, evidence_id) DO UPDATE SET
                    link_type = excluded.link_type,
                    confidence = excluded.confidence
            """, [link_id, claim_id, evidence_id, link_type, confidence, created_by])
            
            self._log_provenance(
                entity_type='link',
                entity_id=link_id,
                action='create',
                actor=created_by,
                details={'claim_id': claim_id, 'evidence_id': evidence_id, 'type': link_type}
            )
            
        finally:
            conn.close()
        
        logger.debug(f"Linked evidence {evidence_id} to claim {claim_id} ({link_type})")
        return link_id
    
    def search_semantic(
        self,
        query: str,
        n_results: int = 10,
        where: Optional[Dict[str, Any]] = None
    ) -> List[SearchResult]:
        """
        Search evidence using semantic similarity.
        
        Args:
            query: Search query
            n_results: Maximum results
            where: Metadata filter
            
        Returns:
            List of search results
        """
        return self._vector_store.search(
            collection_type=CollectionType.EVIDENCE,
            query=query,
            case_id=self.case_id,
            n_results=n_results,
            where=where
        )
    
    def search_hybrid(
        self,
        query: str,
        n_results: int = 10,
        semantic_weight: float = 0.7,
        keyword_weight: float = 0.3,
        where: Optional[Dict[str, Any]] = None
    ) -> List[HybridSearchResult]:
        """
        Hybrid search combining semantic and keyword matching.
        
        Args:
            query: Search query
            n_results: Maximum results
            semantic_weight: Weight for semantic similarity (0-1)
            keyword_weight: Weight for keyword matching (0-1)
            where: Metadata filter
            
        Returns:
            List of hybrid search results
        """
        # Semantic search
        semantic_results = self.search_semantic(query, n_results * 2, where)
        
        # BM25 keyword search
        keyword_results = self._search_bm25(query, n_results * 2)
        
        # Combine scores
        combined = {}
        
        for r in semantic_results:
            combined[r.id] = {
                'content': r.content,
                'semantic_score': r.score,
                'keyword_score': 0.0,
                'metadata': r.metadata
            }
        
        for eid, score in keyword_results:
            if eid in combined:
                combined[eid]['keyword_score'] = score
            else:
                # Get content from DB
                evidence = self.get_evidence(eid)
                if evidence:
                    combined[eid] = {
                        'content': evidence.content,
                        'semantic_score': 0.0,
                        'keyword_score': score,
                        'metadata': evidence.metadata
                    }
        
        # Calculate combined scores
        results = []
        for eid, data in combined.items():
            combined_score = (
                data['semantic_score'] * semantic_weight +
                data['keyword_score'] * keyword_weight
            )
            results.append(HybridSearchResult(
                evidence_id=eid,
                content=data['content'],
                semantic_score=data['semantic_score'],
                keyword_score=data['keyword_score'],
                combined_score=combined_score,
                metadata=data['metadata']
            ))
        
        # Sort by combined score
        results.sort(key=lambda x: x.combined_score, reverse=True)
        return results[:n_results]
    
    def _search_bm25(self, query: str, n_results: int = 10) -> List[Tuple[str, float]]:
        """BM25 keyword search."""
        try:
            from rank_bm25 import BM25Okapi
            
            # Get all evidence for this case
            conn = open_vault(self.case_id)
            try:
                rows = conn.execute("""
                    SELECT evidence_id, content FROM evidence_registry
                    WHERE case_id = ?
                """, [self.case_id]).fetchall()
            finally:
                conn.close()
            
            if not rows:
                return []
            
            # Tokenize
            corpus = [r[1].lower().split() for r in rows]
            doc_ids = [r[0] for r in rows]
            
            # Build BM25 index
            bm25 = BM25Okapi(corpus)
            
            # Search
            query_tokens = query.lower().split()
            scores = bm25.get_scores(query_tokens)
            
            # Normalize scores
            max_score = max(scores) if scores.any() else 1.0
            if max_score > 0:
                scores = scores / max_score
            
            # Get top results
            results = [(doc_ids[i], float(scores[i])) for i in range(len(scores))]
            results.sort(key=lambda x: x[1], reverse=True)
            
            return results[:n_results]
            
        except ImportError:
            logger.warning("rank_bm25 not installed, falling back to semantic only")
            return []
        except Exception as e:
            logger.error(f"BM25 search failed: {e}")
            return []
    
    def get_evidence(self, evidence_id: str) -> Optional[EvidenceItem]:
        """Get evidence by ID."""
        conn = open_vault(self.case_id)
        try:
            row = conn.execute("""
                SELECT evidence_id, case_id, content, evidence_type, source,
                       confidence, content_hash, embedding_id, created_at, metadata
                FROM evidence_registry
                WHERE evidence_id = ?
            """, [evidence_id]).fetchone()
            
            if not row:
                return None
            
            return EvidenceItem(
                evidence_id=row[0],
                case_id=row[1],
                content=row[2],
                evidence_type=row[3],
                source=row[4],
                confidence=row[5],
                hash=row[6],
                embedding_id=row[7],
                created_at=row[8] if row[8] else datetime.now(timezone.utc),
                metadata=json.loads(row[9]) if row[9] else {}
            )
        finally:
            conn.close()
    
    def get_evidence_for_claim(self, claim_id: str) -> List[Dict[str, Any]]:
        """Get all evidence linked to a claim."""
        conn = open_vault(self.case_id)
        try:
            rows = conn.execute("""
                SELECT e.evidence_id, e.content, e.evidence_type, e.source,
                       e.confidence as evidence_confidence,
                       el.link_type, el.confidence as link_confidence
                FROM evidence_registry e
                JOIN evidence_links el ON e.evidence_id = el.evidence_id
                WHERE el.claim_id = ?
                ORDER BY el.confidence DESC
            """, [claim_id]).fetchall()
            
            return [
                {
                    'evidence_id': r[0],
                    'content': r[1],
                    'evidence_type': r[2],
                    'source': r[3],
                    'evidence_confidence': r[4],
                    'link_type': r[5],
                    'link_confidence': r[6]
                }
                for r in rows
            ]
        finally:
            conn.close()
    
    def get_claims_for_evidence(self, evidence_id: str) -> List[Dict[str, Any]]:
        """Get all claims linked to an evidence item."""
        conn = open_vault(self.case_id)
        try:
            rows = conn.execute("""
                SELECT el.claim_id, el.link_type, el.confidence, el.created_by
                FROM evidence_links el
                WHERE el.evidence_id = ?
            """, [evidence_id]).fetchall()
            
            return [
                {
                    'claim_id': r[0],
                    'link_type': r[1],
                    'confidence': r[2],
                    'created_by': r[3]
                }
                for r in rows
            ]
        finally:
            conn.close()
    
    def get_provenance(
        self,
        entity_type: Optional[str] = None,
        entity_id: Optional[str] = None,
        limit: int = 100
    ) -> List[ProvenanceEntry]:
        """Get provenance log entries."""
        conn = open_vault(self.case_id)
        try:
            conditions = []
            params = []
            
            if entity_type:
                conditions.append("entity_type = ?")
                params.append(entity_type)
            if entity_id:
                conditions.append("entity_id = ?")
                params.append(entity_id)
            
            where_clause = f"WHERE {' AND '.join(conditions)}" if conditions else ""
            
            rows = conn.execute(f"""
                SELECT entry_id, entity_type, entity_id, action, actor, timestamp, details
                FROM evidence_provenance
                {where_clause}
                ORDER BY timestamp DESC
                LIMIT ?
            """, params + [limit]).fetchall()
            
            return [
                ProvenanceEntry(
                    entry_id=r[0],
                    entity_type=r[1],
                    entity_id=r[2],
                    action=r[3],
                    actor=r[4],
                    timestamp=r[5],
                    details=json.loads(r[6]) if r[6] else {}
                )
                for r in rows
            ]
        finally:
            conn.close()
    
    def _log_provenance(
        self,
        entity_type: str,
        entity_id: str,
        action: str,
        actor: str = "system",
        details: Optional[Dict[str, Any]] = None
    ) -> None:
        """Log a provenance entry."""
        entry_id = f"prov_{uuid.uuid4().hex[:12]}"
        
        conn = open_vault(self.case_id)
        try:
            conn.execute("""
                INSERT INTO evidence_provenance (
                    entry_id, entity_type, entity_id, action, actor, details
                ) VALUES (?, ?, ?, ?, ?, ?)
            """, [
                entry_id,
                entity_type,
                entity_id,
                action,
                actor,
                json.dumps(details) if details else None
            ])
        finally:
            conn.close()
    
    def get_stats(self) -> Dict[str, Any]:
        """Get evidence vault statistics."""
        conn = open_vault(self.case_id)
        try:
            evidence_count = conn.execute("""
                SELECT COUNT(*) FROM evidence_registry WHERE case_id = ?
            """, [self.case_id]).fetchone()[0]
            
            link_count = conn.execute("""
                SELECT COUNT(*) FROM evidence_links el
                JOIN evidence_registry e ON el.evidence_id = e.evidence_id
                WHERE e.case_id = ?
            """, [self.case_id]).fetchone()[0]
            
            type_breakdown = conn.execute("""
                SELECT evidence_type, COUNT(*) as count
                FROM evidence_registry
                WHERE case_id = ?
                GROUP BY evidence_type
                ORDER BY count DESC
            """, [self.case_id]).fetchall()
            
            # Vector store stats
            try:
                vector_stats = self._vector_store.get_collection_stats(
                    CollectionType.EVIDENCE, self.case_id
                )
                vector_count = vector_stats.count
            except:
                vector_count = 0
            
            return {
                'total_evidence': evidence_count,
                'total_links': link_count,
                'vector_embeddings': vector_count,
                'by_type': [{'type': r[0], 'count': r[1]} for r in type_breakdown]
            }
        finally:
            conn.close()


# Global registry
_evidence_vaults: Dict[str, EvidenceVault] = {}


def get_evidence_vault(case_id: str) -> EvidenceVault:
    """Get or create evidence vault for a case."""
    if case_id not in _evidence_vaults:
        _evidence_vaults[case_id] = EvidenceVault(case_id)
    return _evidence_vaults[case_id]

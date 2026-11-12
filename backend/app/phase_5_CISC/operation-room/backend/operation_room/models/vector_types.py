"""
Vector Types for Oracle 26AI Open-Source Implementation.

Pydantic models for vector operations - embeddings, search, collections.
"""

from datetime import datetime
from enum import Enum
from typing import Any, Dict, List, Optional, Union
from pydantic import BaseModel, Field


class CollectionTypeEnum(str, Enum):
    """Types of vector collections."""
    EVIDENCE = "evidence"
    SESSION = "session"
    HYPOTHESIS = "hypothesis"
    TEMPLATES = "templates"
    CALIBRATION = "calibration"


class VectorDocumentModel(BaseModel):
    """Document to store in vector database."""
    id: Optional[str] = Field(None, description="Document ID (auto-generated if not provided)")
    content: str = Field(..., description="Text content to embed")
    embedding: Optional[List[float]] = Field(None, description="Pre-computed embedding vector")
    metadata: Dict[str, Any] = Field(default_factory=dict, description="Additional metadata")
    
    class Config:
        json_schema_extra = {
            "example": {
                "id": "ev-001",
                "content": "Suspicious login attempt from IP 192.168.1.100",
                "metadata": {
                    "source": "auth_log",
                    "timestamp": "2024-01-15T10:30:00Z",
                    "severity": "HIGH"
                }
            }
        }


class SearchResultModel(BaseModel):
    """Result from vector similarity search."""
    id: str = Field(..., description="Document ID")
    content: str = Field(..., description="Document content")
    score: float = Field(..., description="Similarity score (0-1)")
    metadata: Dict[str, Any] = Field(default_factory=dict, description="Document metadata")
    
    class Config:
        json_schema_extra = {
            "example": {
                "id": "ev-001",
                "content": "Suspicious login attempt from IP 192.168.1.100",
                "score": 0.89,
                "metadata": {"source": "auth_log", "severity": "HIGH"}
            }
        }


class CollectionStatsModel(BaseModel):
    """Statistics for a vector collection."""
    name: str = Field(..., description="Collection name")
    count: int = Field(..., description="Number of documents")
    embedding_dimension: int = Field(..., description="Embedding vector dimension")
    case_id: Optional[str] = Field(None, description="Case ID (if per-case collection)")


class EmbeddingRequest(BaseModel):
    """Request to generate embeddings."""
    texts: List[str] = Field(..., description="Texts to embed")
    
    class Config:
        json_schema_extra = {
            "example": {
                "texts": ["First document", "Second document"]
            }
        }


class EmbeddingResponse(BaseModel):
    """Response with generated embeddings."""
    embeddings: List[List[float]] = Field(..., description="List of embedding vectors")
    model: str = Field(..., description="Model used for embedding")
    dimension: int = Field(..., description="Embedding dimension")


class AddDocumentRequest(BaseModel):
    """Request to add a document to vector store."""
    collection_type: CollectionTypeEnum = Field(..., description="Collection type")
    content: str = Field(..., description="Document content")
    metadata: Optional[Dict[str, Any]] = Field(None, description="Optional metadata")
    doc_id: Optional[str] = Field(None, description="Optional document ID")
    case_id: Optional[str] = Field(None, description="Case ID (required for per-case collections)")


class AddDocumentResponse(BaseModel):
    """Response after adding a document."""
    doc_id: str = Field(..., description="Document ID")
    collection: str = Field(..., description="Collection name")


class SearchRequest(BaseModel):
    """Request for vector similarity search."""
    collection_type: CollectionTypeEnum = Field(..., description="Collection to search")
    query: str = Field(..., description="Query text")
    case_id: Optional[str] = Field(None, description="Case ID (required for per-case collections)")
    n_results: int = Field(10, ge=1, le=100, description="Maximum results to return")
    where: Optional[Dict[str, Any]] = Field(None, description="Metadata filter (ChromaDB syntax)")
    
    class Config:
        json_schema_extra = {
            "example": {
                "collection_type": "evidence",
                "query": "suspicious network activity",
                "case_id": "CASE-001",
                "n_results": 5,
                "where": {"severity": "HIGH"}
            }
        }


class SearchResponse(BaseModel):
    """Response from vector similarity search."""
    results: List[SearchResultModel] = Field(..., description="Search results")
    query: str = Field(..., description="Original query")
    total: int = Field(..., description="Number of results returned")


class HybridSearchRequest(BaseModel):
    """Request for hybrid search (semantic + keyword)."""
    collection_type: CollectionTypeEnum = Field(..., description="Collection to search")
    query: str = Field(..., description="Query text")
    case_id: Optional[str] = Field(None, description="Case ID")
    n_results: int = Field(10, ge=1, le=100, description="Maximum results")
    semantic_weight: float = Field(0.7, ge=0, le=1, description="Weight for semantic search (0-1)")
    keyword_weight: float = Field(0.3, ge=0, le=1, description="Weight for keyword search (0-1)")
    where: Optional[Dict[str, Any]] = Field(None, description="Metadata filter")


class EvidenceLinkModel(BaseModel):
    """Link between claim/text and supporting evidence."""
    claim_id: str = Field(..., description="Claim/statement ID")
    evidence_id: str = Field(..., description="Evidence document ID")
    link_type: str = Field("supports", description="Link type: supports, contradicts, related")
    confidence: float = Field(0.5, ge=0, le=1, description="Link confidence score")
    created_at: datetime = Field(default_factory=datetime.utcnow)
    
    class Config:
        json_schema_extra = {
            "example": {
                "claim_id": "claim-001",
                "evidence_id": "ev-001",
                "link_type": "supports",
                "confidence": 0.85
            }
        }


class ProvenanceRecord(BaseModel):
    """Record of data provenance for audit trail."""
    record_id: str = Field(..., description="Unique record ID")
    entity_type: str = Field(..., description="Type: evidence, claim, hypothesis, report")
    entity_id: str = Field(..., description="Entity ID")
    action: str = Field(..., description="Action: create, update, link, validate")
    actor: str = Field("system", description="Who performed the action")
    timestamp: datetime = Field(default_factory=datetime.utcnow)
    details: Dict[str, Any] = Field(default_factory=dict, description="Action details")


class ValidationClaimModel(BaseModel):
    """A claim extracted from report text for validation."""
    claim_id: str = Field(..., description="Unique claim ID")
    text: str = Field(..., description="Claim text")
    source_section: str = Field(..., description="Section where claim appears")
    claim_type: str = Field("factual", description="Type: factual, temporal, quantitative, causal")
    extracted_at: datetime = Field(default_factory=datetime.utcnow)
    supporting_evidence: List[str] = Field(default_factory=list, description="List of evidence IDs")
    confidence: float = Field(0.0, ge=0, le=1, description="Validation confidence")
    is_supported: Optional[bool] = Field(None, description="Whether claim is evidence-supported")


class ClaimValidationResult(BaseModel):
    """Result of validating a claim against evidence."""
    claim_id: str
    is_supported: bool
    confidence: float
    supporting_evidence: List[str]
    contradicting_evidence: List[str]
    validation_notes: str = ""

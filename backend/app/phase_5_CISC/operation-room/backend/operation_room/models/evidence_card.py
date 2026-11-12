from pydantic import BaseModel, Field
from typing import List, Literal, Optional
import uuid

class Claim(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    status: Literal["draft", "review", "approved"] = "draft"
    text: str
    evidence_card_ids: List[str] = Field(default_factory=list)

class EvidenceRef(BaseModel):
    case_id: str
    table: str
    pointers: List[str] = Field(description="List of event IDs")
    rowHashes: List[str] = Field(description="SHA-256 hashes of the respective rows")

class EvidenceCard(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    title: str
    description: Optional[str] = None
    evidence_ref: EvidenceRef
    hash: Optional[str] = None # Canonical hash of the card
    artifact_path: Optional[str] = None # Path to frozen snapshot evidence

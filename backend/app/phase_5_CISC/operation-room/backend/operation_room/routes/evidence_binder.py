from fastapi import APIRouter, HTTPException, Path
from pydantic import BaseModel
import duckdb
import os
import hashlib
from canonicaljson import encode_canonical_json
from typing import List

from operation_room.models.evidence_card import EvidenceCard
from operation_room.config import settings
from operation_room.services.audit_service import record_coc_event
from operation_room.services.snapshot_service import freeze_evidence
from operation_room.database import get_vault_path

router = APIRouter(prefix="/api/cases", tags=["Evidence Binder"])

@router.post("/{case_id}/evidence-cards", response_model=EvidenceCard)
async def create_evidence_card(
    evidence_card: EvidenceCard,
    case_id: str = Path(...)
):
    vault_db = get_vault_path(case_id)
    if not vault_db.exists():
        raise HTTPException(404, "Vault not found")

    # [NEW SNAPSHOT ENGINE] Capture the physical artifact immutably
    artifact_path = freeze_evidence(
        case_id=case_id,
        card_id=evidence_card.id,
        table=evidence_card.evidence_ref.table,
        pointers=evidence_card.evidence_ref.pointers
    )
    evidence_card.artifact_path = artifact_path

    card_dict = evidence_card.dict(exclude={"hash"})
    # Generate RFC 8785 canonical hash
    canonical_data = encode_canonical_json(card_dict)
    card_hash = hashlib.sha256(canonical_data).hexdigest()

    evidence_card.hash = card_hash

    from operation_room.database import open_vault
    con = open_vault(case_id)
    try:
        # Create table if not exists
        con.execute("""
            CREATE TABLE IF NOT EXISTS evidence_binder (
                id VARCHAR PRIMARY KEY,
                title VARCHAR,
                description VARCHAR,
                card_hash VARCHAR,
                evidence_ref JSON,
                artifact_path VARCHAR
            )
        """)

        # Insert evidence card
        con.execute(
            "INSERT INTO evidence_binder (id, title, description, card_hash, evidence_ref, artifact_path) VALUES (?, ?, ?, ?, ?, ?)",
            [evidence_card.id, evidence_card.title, evidence_card.description, evidence_card.hash, evidence_card.evidence_ref.json(), evidence_card.artifact_path]
        )

        # Emit CoC event
        record_coc_event(
            case_id=case_id,
            action="ADDED_EVIDENCE_CARD",
            actor="investigator", # Mock user
            target_artefact=f"evidence_card:{evidence_card.id}",
            details={
                "card_id": evidence_card.id,
                "card_hash": evidence_card.hash
            }
        )
        
        return evidence_card
    except Exception as e:
        raise HTTPException(500, f"Database error: {str(e)}")
    finally:
        con.close()

@router.get("/{case_id}/evidence-cards", response_model=List[EvidenceCard])
async def list_evidence_cards(case_id: str = Path(...)):
    vault_db = get_vault_path(case_id)
    if not vault_db.exists():
        raise HTTPException(404, "Vault not found")
        
    from operation_room.database import open_vault
    con = open_vault(case_id)
    try:
        try:
            cards = con.execute("SELECT id, title, description, card_hash, evidence_ref, artifact_path FROM evidence_binder").fetchall()
        except duckdb.CatalogException:
            # Table doesn't exist yet
            return []

        import json
        result = []
        for card in cards:
            result.append(EvidenceCard(
                id=card[0],
                title=card[1],
                description=card[2],
                hash=card[3],
                evidence_ref=json.loads(card[4]),
                artifact_path=card[5] if len(card) > 5 else None
            ))
        return result
    except Exception as e:
        raise HTTPException(500, f"Database error: {str(e)}")
    finally:
        con.close()

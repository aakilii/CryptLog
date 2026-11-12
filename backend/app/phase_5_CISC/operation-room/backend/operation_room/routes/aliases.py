"""
Entity Alias API Routes

Provides REST endpoints for managing entity aliases in the Evidence Vault.
"""

from fastapi import APIRouter, HTTPException
from typing import List, Dict, Any, Optional
from pydantic import BaseModel

from operation_room.services.entity_alias_service import (
    entity_alias_service,
    EntityType,
)


router = APIRouter(prefix="/api/aliases", tags=["aliases"])


# ═══════════════════════════════════════════════════════════════════════════════
# REQUEST/RESPONSE MODELS
# ═══════════════════════════════════════════════════════════════════════════════

class SetAliasRequest(BaseModel):
    """Request to set an entity alias."""
    entity_value: str
    alias: str
    entity_type: str  # "ip", "mac", "user", etc.
    notes: Optional[str] = ""


class AutoAliasRequest(BaseModel):
    """Request to auto-generate alias."""
    entity_value: str
    entity_type: Optional[str] = None


class BulkImportRequest(BaseModel):
    """Request to import multiple aliases."""
    aliases: List[Dict[str, Any]]


class FormatTextRequest(BaseModel):
    """Request to format text with aliases."""
    text: str
    show_alias_inline: bool = False


class SuggestRequest(BaseModel):
    """Request for alias suggestions."""
    entities: List[str]


class AliasResponse(BaseModel):
    """Response for a single alias."""
    alias_id: str
    entity_value: str
    alias: str
    entity_type: str
    case_id: str
    created_at: str
    created_by: str
    notes: str
    auto_generated: bool


# ═══════════════════════════════════════════════════════════════════════════════
# ENDPOINTS
# ═══════════════════════════════════════════════════════════════════════════════

@router.get("/{case_id}", response_model=List[AliasResponse])
async def get_all_aliases(case_id: str):
    """Get all aliases for a case."""
    aliases = entity_alias_service.get_all_aliases(case_id)
    return [a.to_dict() for a in aliases]


@router.get("/{case_id}/by-type/{entity_type}", response_model=List[AliasResponse])
async def get_aliases_by_type(case_id: str, entity_type: str):
    """Get aliases filtered by entity type."""
    try:
        etype = EntityType(entity_type)
    except ValueError:
        raise HTTPException(status_code=400, detail=f"Invalid entity type: {entity_type}")
    
    aliases = entity_alias_service.get_aliases_by_type(case_id, etype)
    return [a.to_dict() for a in aliases]


@router.get("/{case_id}/resolve/{entity_value:path}")
async def resolve_alias(case_id: str, entity_value: str):
    """Resolve an entity value to its alias."""
    alias = entity_alias_service.resolve(case_id, entity_value)
    full_alias = entity_alias_service.get_alias(case_id, entity_value)
    
    return {
        "entity_value": entity_value,
        "resolved": alias,
        "has_alias": full_alias is not None,
        "alias_info": full_alias.to_dict() if full_alias else None,
    }


@router.get("/{case_id}/tooltip/{entity_value:path}")
async def get_tooltip(case_id: str, entity_value: str):
    """Get tooltip data for an entity value."""
    tooltip = entity_alias_service.get_entity_tooltip(case_id, entity_value)
    
    if not tooltip:
        return {"found": False, "entity_value": entity_value}
    
    return {"found": True, "entity_value": entity_value, **tooltip}


@router.post("/{case_id}/set", response_model=AliasResponse)
async def set_alias(case_id: str, request: SetAliasRequest):
    """Set an alias for an entity."""
    try:
        etype = EntityType(request.entity_type)
    except ValueError:
        raise HTTPException(status_code=400, detail=f"Invalid entity type: {request.entity_type}")
    
    alias = entity_alias_service.set_alias(
        case_id=case_id,
        entity_value=request.entity_value,
        alias=request.alias,
        entity_type=etype,
        created_by="user",
        notes=request.notes or "",
    )
    
    return alias.to_dict()


@router.post("/{case_id}/auto", response_model=AliasResponse)
async def auto_alias(case_id: str, request: AutoAliasRequest):
    """Auto-generate an alias for an entity."""
    etype = None
    if request.entity_type:
        try:
            etype = EntityType(request.entity_type)
        except ValueError:
            raise HTTPException(status_code=400, detail=f"Invalid entity type: {request.entity_type}")
    
    alias = entity_alias_service.auto_alias(
        case_id=case_id,
        entity_value=request.entity_value,
        entity_type=etype,
    )
    
    return alias.to_dict()


@router.delete("/{case_id}/{entity_value:path}")
async def delete_alias(case_id: str, entity_value: str):
    """Delete an alias."""
    success = entity_alias_service.delete_alias(case_id, entity_value)
    
    if not success:
        raise HTTPException(status_code=404, detail=f"Alias not found: {entity_value}")
    
    return {"deleted": True, "entity_value": entity_value}


@router.post("/{case_id}/import")
async def bulk_import(case_id: str, request: BulkImportRequest):
    """Import multiple aliases at once."""
    count = entity_alias_service.bulk_import(case_id, request.aliases)
    
    return {
        "imported": count,
        "total_requested": len(request.aliases),
    }


@router.get("/{case_id}/export")
async def export_aliases(case_id: str):
    """Export all aliases for a case."""
    aliases = entity_alias_service.export_aliases(case_id)
    
    return {
        "case_id": case_id,
        "count": len(aliases),
        "aliases": aliases,
    }


@router.post("/{case_id}/format")
async def format_text(case_id: str, request: FormatTextRequest):
    """Format text with alias replacements."""
    formatted, entities = entity_alias_service.format_for_report(
        case_id=case_id,
        text=request.text,
        show_alias_inline=request.show_alias_inline,
    )
    
    return {
        "original": request.text,
        "formatted": formatted,
        "entities_found": entities,
    }


@router.post("/{case_id}/suggest")
async def suggest_aliases(case_id: str, request: SuggestRequest):
    """Get alias suggestions for entities."""
    suggestions = entity_alias_service.suggest_aliases(
        case_id=case_id,
        entities=request.entities,
    )
    
    return {
        "suggestions": suggestions,
        "count": len(suggestions),
    }

"""
Entity Alias Service

Manages entity aliases for the Evidence Vault:
- IP addresses → friendly names (e.g., "suspicious_user_1")
- MAC addresses → device names
- User IDs → role identifiers
- Hostnames → labels

Features:
- Auto-alias generation for common patterns
- Alias resolution for reports (show original with alias tooltip)
- Bulk import/export
- Alias suggestions based on evidence patterns
"""

import logging
import re
from typing import Dict, Any, List, Optional, Tuple
from datetime import datetime
from dataclasses import dataclass, field
from enum import Enum
import hashlib
import json

logger = logging.getLogger(__name__)


class EntityType(str, Enum):
    """Types of entities that can be aliased."""
    IP = "ip"
    MAC = "mac"
    USER = "user"
    HOST = "host"
    FILE = "file"
    EMAIL = "email"
    PROCESS = "process"


@dataclass
class EntityAlias:
    """An entity alias record."""
    entity_value: str           # Original value (e.g., "192.168.1.45")
    alias: str                  # Friendly name (e.g., "suspicious_user_1")
    entity_type: EntityType     # Type of entity
    case_id: str               # Case this alias belongs to
    created_at: str = field(default_factory=lambda: datetime.now().isoformat())
    created_by: str = "system"
    notes: str = ""
    auto_generated: bool = False
    
    @property
    def alias_id(self) -> str:
        """Generate unique ID for this alias."""
        content = f"{self.case_id}:{self.entity_type.value}:{self.entity_value}"
        return hashlib.md5(content.encode()).hexdigest()[:12]
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "alias_id": self.alias_id,
            "entity_value": self.entity_value,
            "alias": self.alias,
            "entity_type": self.entity_type.value,
            "case_id": self.case_id,
            "created_at": self.created_at,
            "created_by": self.created_by,
            "notes": self.notes,
            "auto_generated": self.auto_generated,
        }


class EntityAliasService:
    """
    Service for managing entity aliases.
    
    Integrates with Evidence Vault to provide friendly names
    for technical identifiers in reports.
    """
    
    def __init__(self):
        # In-memory store (would be DB-backed in production)
        self._aliases: Dict[str, Dict[str, EntityAlias]] = {}  # case_id -> {entity_value -> alias}
        self._counters: Dict[str, Dict[str, int]] = {}  # case_id -> {entity_type -> counter}
    
    def _get_case_aliases(self, case_id: str) -> Dict[str, EntityAlias]:
        """Get or create alias store for a case."""
        if case_id not in self._aliases:
            self._aliases[case_id] = {}
            self._counters[case_id] = {t.value: 0 for t in EntityType}
        return self._aliases[case_id]
    
    def set_alias(
        self,
        case_id: str,
        entity_value: str,
        alias: str,
        entity_type: EntityType,
        created_by: str = "user",
        notes: str = "",
    ) -> EntityAlias:
        """
        Set an alias for an entity.
        
        Args:
            case_id: Case ID
            entity_value: Original value (e.g., IP address)
            alias: Friendly name
            entity_type: Type of entity
            created_by: Who created this alias
            notes: Optional notes
        
        Returns:
            The created/updated EntityAlias
        """
        aliases = self._get_case_aliases(case_id)
        
        entity_alias = EntityAlias(
            entity_value=entity_value,
            alias=alias,
            entity_type=entity_type,
            case_id=case_id,
            created_by=created_by,
            notes=notes,
            auto_generated=False,
        )
        
        aliases[entity_value] = entity_alias
        logger.info(f"Set alias: {entity_value} → {alias} ({entity_type.value})")
        
        return entity_alias
    
    def get_alias(self, case_id: str, entity_value: str) -> Optional[EntityAlias]:
        """Get alias for an entity value."""
        aliases = self._get_case_aliases(case_id)
        return aliases.get(entity_value)
    
    def resolve(self, case_id: str, entity_value: str) -> str:
        """
        Resolve entity to alias if exists, otherwise return original.
        
        Args:
            case_id: Case ID
            entity_value: Entity to resolve
        
        Returns:
            Alias if exists, else original value
        """
        alias = self.get_alias(case_id, entity_value)
        return alias.alias if alias else entity_value
    
    def get_all_aliases(self, case_id: str) -> List[EntityAlias]:
        """Get all aliases for a case."""
        aliases = self._get_case_aliases(case_id)
        return list(aliases.values())
    
    def get_aliases_by_type(self, case_id: str, entity_type: EntityType) -> List[EntityAlias]:
        """Get aliases filtered by type."""
        aliases = self._get_case_aliases(case_id)
        return [a for a in aliases.values() if a.entity_type == entity_type]
    
    def delete_alias(self, case_id: str, entity_value: str) -> bool:
        """Delete an alias."""
        aliases = self._get_case_aliases(case_id)
        if entity_value in aliases:
            del aliases[entity_value]
            return True
        return False
    
    def auto_alias(
        self,
        case_id: str,
        entity_value: str,
        entity_type: Optional[EntityType] = None,
    ) -> EntityAlias:
        """
        Auto-generate an alias for an entity.
        
        Args:
            case_id: Case ID
            entity_value: Entity value to alias
            entity_type: Type (auto-detected if not provided)
        
        Returns:
            Generated EntityAlias
        """
        # Auto-detect type if not provided
        if entity_type is None:
            entity_type = self._detect_entity_type(entity_value)
        
        # Check if already aliased
        existing = self.get_alias(case_id, entity_value)
        if existing:
            return existing
        
        # Generate alias
        counters = self._counters.get(case_id, {})
        if case_id not in self._counters:
            self._counters[case_id] = {t.value: 0 for t in EntityType}
            counters = self._counters[case_id]
        
        counter = counters.get(entity_type.value, 0) + 1
        counters[entity_type.value] = counter
        
        # Generate alias based on type
        alias = self._generate_alias(entity_type, counter, entity_value)
        
        entity_alias = EntityAlias(
            entity_value=entity_value,
            alias=alias,
            entity_type=entity_type,
            case_id=case_id,
            created_by="system",
            auto_generated=True,
        )
        
        aliases = self._get_case_aliases(case_id)
        aliases[entity_value] = entity_alias
        
        logger.info(f"Auto-aliased: {entity_value} → {alias} ({entity_type.value})")
        return entity_alias
    
    def _detect_entity_type(self, value: str) -> EntityType:
        """Auto-detect entity type from value."""
        # IP address patterns
        if re.match(r'^\d{1,3}\.\d{1,3}\.\d{1,3}\.\d{1,3}$', value):
            return EntityType.IP
        
        # IPv6
        if ':' in value and re.match(r'^[0-9a-fA-F:]+$', value):
            return EntityType.IP
        
        # MAC address
        if re.match(r'^([0-9a-fA-F]{2}[:-]){5}[0-9a-fA-F]{2}$', value):
            return EntityType.MAC
        
        # Email
        if '@' in value and '.' in value:
            return EntityType.EMAIL
        
        # File path
        if '/' in value or '\\' in value:
            return EntityType.FILE
        
        # Default to user
        return EntityType.USER
    
    def _generate_alias(self, entity_type: EntityType, counter: int, value: str) -> str:
        """Generate alias based on type and counter."""
        prefixes = {
            EntityType.IP: "host",
            EntityType.MAC: "device",
            EntityType.USER: "user",
            EntityType.HOST: "server",
            EntityType.FILE: "file",
            EntityType.EMAIL: "contact",
            EntityType.PROCESS: "proc",
        }
        
        prefix = prefixes.get(entity_type, "entity")
        
        # Add suffix based on value characteristics
        suffix = ""
        if entity_type == EntityType.IP:
            # External vs internal
            if value.startswith("192.168.") or value.startswith("10.") or value.startswith("172."):
                suffix = "_internal"
            else:
                suffix = "_external"
        
        return f"{prefix}_{counter:02d}{suffix}"
    
    def bulk_import(self, case_id: str, aliases: List[Dict[str, Any]]) -> int:
        """
        Import multiple aliases at once.
        
        Args:
            case_id: Case ID
            aliases: List of alias dicts with entity_value, alias, entity_type
        
        Returns:
            Number of aliases imported
        """
        count = 0
        for alias_data in aliases:
            try:
                self.set_alias(
                    case_id=case_id,
                    entity_value=alias_data["entity_value"],
                    alias=alias_data["alias"],
                    entity_type=EntityType(alias_data["entity_type"]),
                    created_by=alias_data.get("created_by", "import"),
                    notes=alias_data.get("notes", ""),
                )
                count += 1
            except Exception as e:
                logger.error(f"Failed to import alias: {e}")
        
        return count
    
    def export_aliases(self, case_id: str) -> List[Dict[str, Any]]:
        """Export all aliases for a case."""
        aliases = self.get_all_aliases(case_id)
        return [a.to_dict() for a in aliases]
    
    def format_for_report(
        self,
        case_id: str,
        text: str,
        show_alias_inline: bool = False,
    ) -> Tuple[str, List[Dict[str, Any]]]:
        """
        Format text for report, replacing entities with formatted versions.
        
        Args:
            case_id: Case ID
            text: Text containing entity values
            show_alias_inline: If True, show "value (alias)"; if False, just value
        
        Returns:
            Tuple of (formatted_text, list of entities found)
        """
        aliases = self._get_case_aliases(case_id)
        entities_found = []
        formatted_text = text
        
        for entity_value, alias in aliases.items():
            if entity_value in text:
                entities_found.append({
                    "value": entity_value,
                    "alias": alias.alias,
                    "type": alias.entity_type.value,
                })
                
                if show_alias_inline:
                    replacement = f"{entity_value} ({alias.alias})"
                    formatted_text = formatted_text.replace(entity_value, replacement)
        
        return formatted_text, entities_found
    
    def get_entity_tooltip(self, case_id: str, entity_value: str) -> Optional[Dict[str, Any]]:
        """
        Get tooltip data for an entity value.
        
        Used by frontend to show hover information.
        
        Returns:
            Dict with alias info and metadata, or None if no alias
        """
        alias = self.get_alias(case_id, entity_value)
        if not alias:
            return None
        
        return {
            "alias": alias.alias,
            "type": alias.entity_type.value,
            "notes": alias.notes,
            "auto_generated": alias.auto_generated,
            "created_at": alias.created_at,
            "created_by": alias.created_by,
        }
    
    def suggest_aliases(self, case_id: str, entities: List[str]) -> List[Dict[str, Any]]:
        """
        Suggest aliases for a list of entities.
        
        Useful for bulk alias generation UI.
        
        Args:
            case_id: Case ID
            entities: List of entity values
        
        Returns:
            List of suggestions with entity_value, suggested_alias, type
        """
        suggestions = []
        
        for entity in entities:
            # Skip if already aliased
            existing = self.get_alias(case_id, entity)
            if existing:
                continue
            
            entity_type = self._detect_entity_type(entity)
            counters = self._counters.get(case_id, {})
            counter = counters.get(entity_type.value, 0) + 1
            suggested = self._generate_alias(entity_type, counter, entity)
            
            suggestions.append({
                "entity_value": entity,
                "suggested_alias": suggested,
                "entity_type": entity_type.value,
            })
        
        return suggestions


# Global service instance
entity_alias_service = EntityAliasService()

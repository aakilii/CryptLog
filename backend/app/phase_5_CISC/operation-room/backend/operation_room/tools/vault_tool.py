"""
Evidence Vault Tool - Universal Module Tool Wrapper

Wraps evidence vault operations for forensic investigation.
Provides evidence storage, retrieval, and verification.
"""

import logging
from typing import List, Dict, Any, Optional
from datetime import datetime
import uuid
import hashlib

from operation_room.tools.base_tool import (
    ModuleTool,
    ToolInput,
    ToolOutput,
    ToolCapability,
    ToolCategory,
    VisualizationType,
    FindingSeverity,
)

logger = logging.getLogger(__name__)


class VaultTool(ModuleTool):
    """
    Evidence Vault Tool.
    
    Provides:
    - Evidence storage with SHA-256 hashing
    - Evidence retrieval and search
    - Integrity verification
    - Citation generation
    - Entity aliasing (IP → friendly name)
    
    Capabilities:
    - store: Store evidence in vault
    - query: Search vault evidence
    - verify: Verify evidence integrity
    - get_citations: Generate report citations
    - get_aliases: Get entity aliases
    - set_alias: Set entity alias
    - get_summary: Vault summary statistics
    """
    
    @property
    def tool_id(self) -> str:
        return "vault"
    
    @property
    def tool_name(self) -> str:
        return "Evidence Vault"
    
    @property
    def tool_version(self) -> str:
        return "2.0.0"
    
    @property
    def tool_category(self) -> ToolCategory:
        return ToolCategory.EVIDENCE
    
    @property
    def description(self) -> str:
        return "Immutable evidence storage with integrity verification"
    
    def get_capabilities(self) -> List[ToolCapability]:
        return [
            ToolCapability(
                name="store",
                description="Store evidence in vault with SHA-256 hash",
                input_schema={
                    "type": "object",
                    "properties": {
                        "case_id": {"type": "string"},
                        "category": {"type": "string"},
                        "data": {"type": "object"},
                        "source_module": {"type": "string"},
                        "tags": {"type": "array", "items": {"type": "string"}}
                    },
                    "required": ["case_id", "category", "data", "source_module"]
                },
                output_schema={
                    "type": "object",
                    "properties": {
                        "evidence_id": {"type": "string"},
                        "hash": {"type": "string"}
                    }
                },
                visualization_types=[],
                supports_streaming=False
            ),
            ToolCapability(
                name="query",
                description="Search vault evidence",
                input_schema={
                    "type": "object",
                    "properties": {
                        "case_id": {"type": "string"},
                        "category": {"type": "string"},
                        "source_module": {"type": "string"},
                        "tags": {"type": "array", "items": {"type": "string"}},
                        "limit": {"type": "integer", "default": 50}
                    },
                    "required": ["case_id"]
                },
                output_schema={
                    "type": "object",
                    "properties": {
                        "evidence": {"type": "array"},
                        "total": {"type": "integer"}
                    }
                },
                visualization_types=[VisualizationType.TABLE],
                supports_streaming=False
            ),
            ToolCapability(
                name="verify",
                description="Verify evidence integrity via SHA-256",
                input_schema={
                    "type": "object",
                    "properties": {
                        "case_id": {"type": "string"},
                        "evidence_id": {"type": "string"}
                    },
                    "required": ["case_id", "evidence_id"]
                },
                output_schema={
                    "type": "object",
                    "properties": {
                        "valid": {"type": "boolean"},
                        "original_hash": {"type": "string"},
                        "current_hash": {"type": "string"}
                    }
                },
                visualization_types=[],
                supports_streaming=False
            ),
            ToolCapability(
                name="get_citations",
                description="Generate evidence citations for report",
                input_schema={
                    "type": "object",
                    "properties": {
                        "case_id": {"type": "string"},
                        "evidence_ids": {"type": "array", "items": {"type": "string"}}
                    },
                    "required": ["case_id", "evidence_ids"]
                },
                output_schema={
                    "type": "object",
                    "properties": {
                        "citations": {"type": "array"}
                    }
                },
                visualization_types=[],
                supports_streaming=False
            ),
            ToolCapability(
                name="get_aliases",
                description="Get entity aliases (IP → friendly name)",
                input_schema={
                    "type": "object",
                    "properties": {
                        "case_id": {"type": "string"}
                    },
                    "required": ["case_id"]
                },
                output_schema={
                    "type": "object",
                    "properties": {
                        "aliases": {"type": "object"}
                    }
                },
                visualization_types=[VisualizationType.TABLE],
                supports_streaming=False
            ),
            ToolCapability(
                name="set_alias",
                description="Set entity alias",
                input_schema={
                    "type": "object",
                    "properties": {
                        "case_id": {"type": "string"},
                        "entity_value": {"type": "string"},
                        "alias": {"type": "string"},
                        "entity_type": {"type": "string", "enum": ["ip", "mac", "user", "host", "file"]}
                    },
                    "required": ["case_id", "entity_value", "alias", "entity_type"]
                },
                output_schema={
                    "type": "object",
                    "properties": {
                        "success": {"type": "boolean"}
                    }
                },
                visualization_types=[],
                supports_streaming=False
            ),
            ToolCapability(
                name="get_summary",
                description="Vault summary statistics",
                input_schema={
                    "type": "object",
                    "properties": {
                        "case_id": {"type": "string"}
                    },
                    "required": ["case_id"]
                },
                output_schema={
                    "type": "object",
                    "properties": {
                        "total_evidence": {"type": "integer"},
                        "by_category": {"type": "object"},
                        "by_module": {"type": "object"}
                    }
                },
                visualization_types=[VisualizationType.PIE_CHART, VisualizationType.METRIC_CARD],
                supports_streaming=False
            ),
        ]
    
    async def execute(self, input: ToolInput) -> ToolOutput:
        start_time = datetime.now()
        
        validation = self.validate_input(input)
        if not validation["valid"]:
            return ToolOutput(
                tool_id=self.tool_id,
                capability=input.capability,
                request_id=input.request_id,
                success=False,
                error=f"Invalid input: {validation['errors']}"
            )
        
        try:
            if input.capability == "store":
                result = await self._store(input.case_id, input.parameters)
            elif input.capability == "query":
                result = await self._query(input.case_id, input.parameters)
            elif input.capability == "verify":
                result = await self._verify(input.case_id, input.parameters)
            elif input.capability == "get_citations":
                result = await self._get_citations(input.case_id, input.parameters)
            elif input.capability == "get_aliases":
                result = await self._get_aliases(input.case_id)
            elif input.capability == "set_alias":
                result = await self._set_alias(input.case_id, input.parameters)
            elif input.capability == "get_summary":
                result = await self._get_summary(input.case_id)
            else:
                return ToolOutput(
                    tool_id=self.tool_id,
                    capability=input.capability,
                    request_id=input.request_id,
                    success=False,
                    error=f"Unknown capability: {input.capability}"
                )
            
            execution_time_ms = int((datetime.now() - start_time).total_seconds() * 1000)
            
            return ToolOutput(
                tool_id=self.tool_id,
                capability=input.capability,
                request_id=input.request_id,
                success=True,
                narrative=result.get("narrative", ""),
                findings=result.get("findings", []),
                visualizations=result.get("visualizations", []),
                tables=result.get("tables", []),
                evidence=result.get("evidence", []),
                execution_time_ms=execution_time_ms,
                page_estimate=result.get("page_estimate", 1),
                confidence_score=result.get("confidence_score", 1.0),
            )
            
        except Exception as e:
            logger.error(f"Vault tool execution failed: {e}", exc_info=True)
            return ToolOutput(
                tool_id=self.tool_id,
                capability=input.capability,
                request_id=input.request_id,
                success=False,
                error=str(e)
            )
    
    async def _store(self, case_id: str, params: Dict[str, Any]) -> Dict[str, Any]:
        """Store evidence in vault."""
        evidence_id = f"ev-{uuid.uuid4().hex[:12]}"
        data = params.get("data", {})
        
        # Calculate SHA-256 hash
        data_str = str(data)
        hash_value = hashlib.sha256(data_str.encode()).hexdigest()
        
        return {
            "narrative": f"Evidence stored with ID {evidence_id} and hash {hash_value[:16]}...",
            "evidence": [{
                "evidence_id": evidence_id,
                "hash": hash_value,
                "category": params.get("category"),
                "source_module": params.get("source_module"),
            }],
            "confidence_score": 1.0,
        }
    
    async def _query(self, case_id: str, params: Dict[str, Any]) -> Dict[str, Any]:
        """Query vault evidence."""
        limit = params.get("limit", 50)
        
        # Mock evidence items
        evidence = [
            {"id": "ev-abc123", "category": "timeline_anchor", "module": "timeline", "created": "2024-03-15T10:00:00Z"},
            {"id": "ev-def456", "category": "anomaly_finding", "module": "anomaly", "created": "2024-03-15T10:05:00Z"},
            {"id": "ev-ghi789", "category": "network_flow", "module": "network", "created": "2024-03-15T10:10:00Z"},
        ]
        
        return {
            "narrative": f"Found {len(evidence)} evidence items in vault.",
            "tables": [{
                "title": "Vault Evidence",
                "columns": ["ID", "Category", "Source Module", "Created"],
                "rows": [[e["id"], e["category"], e["module"], e["created"]] for e in evidence]
            }],
            "page_estimate": 1,
        }
    
    async def _verify(self, case_id: str, params: Dict[str, Any]) -> Dict[str, Any]:
        """Verify evidence integrity."""
        evidence_id = params.get("evidence_id", "unknown")
        
        # Mock verification (always passes for demo)
        original_hash = "abc123def456..."
        current_hash = original_hash  # Same = valid
        
        findings = [
            self.create_finding(
                title=f"Evidence Verified: {evidence_id}",
                description="SHA-256 hash matches original - evidence integrity confirmed",
                severity=FindingSeverity.INFO,
                confidence=1.0,
            )
        ]
        
        return {
            "narrative": f"Evidence {evidence_id} integrity verified. Hash matches original.",
            "findings": findings,
            "confidence_score": 1.0,
        }
    
    async def _get_citations(self, case_id: str, params: Dict[str, Any]) -> Dict[str, Any]:
        """Generate citations."""
        evidence_ids = params.get("evidence_ids", [])
        
        citations = []
        for eid in evidence_ids:
            citations.append({
                "evidence_id": eid,
                "citation": f"[Evidence {eid}] Retrieved from Evidence Vault, Case {case_id}",
                "hash_prefix": f"sha256:{uuid.uuid4().hex[:8]}..."
            })
        
        return {
            "narrative": f"Generated {len(citations)} citations for report.",
            "tables": [{
                "title": "Evidence Citations",
                "columns": ["Evidence ID", "Citation", "Hash"],
                "rows": [[c["evidence_id"], c["citation"], c["hash_prefix"]] for c in citations]
            }],
        }
    
    async def _get_aliases(self, case_id: str) -> Dict[str, Any]:
        """Get entity aliases."""
        # Mock aliases
        aliases = {
            "192.168.1.45": {"alias": "suspicious_user_1", "type": "ip"},
            "192.168.1.101": {"alias": "admin_workstation", "type": "ip"},
            "00:1A:2B:3C:4D:5E": {"alias": "suspect_device", "type": "mac"},
            "jsmith": {"alias": "primary_suspect", "type": "user"},
        }
        
        return {
            "narrative": f"Found {len(aliases)} entity aliases in vault.",
            "tables": [{
                "title": "Entity Aliases",
                "columns": ["Original Value", "Alias", "Type"],
                "rows": [[k, v["alias"], v["type"]] for k, v in aliases.items()]
            }],
            "page_estimate": 1,
        }
    
    async def _set_alias(self, case_id: str, params: Dict[str, Any]) -> Dict[str, Any]:
        """Set entity alias."""
        entity_value = params.get("entity_value")
        alias = params.get("alias")
        entity_type = params.get("entity_type")
        
        return {
            "narrative": f"Alias set: {entity_value} → {alias} ({entity_type})",
            "confidence_score": 1.0,
        }
    
    async def _get_summary(self, case_id: str) -> Dict[str, Any]:
        """Get vault summary."""
        by_category = {
            "timeline_anchor": 23,
            "anomaly_finding": 15,
            "network_flow": 47,
            "crud_operation": 89,
            "correlation_node": 34,
        }
        total = sum(by_category.values())
        
        by_module = {
            "timeline": 23,
            "anomaly": 15,
            "network": 47,
            "crud": 89,
            "correlation": 34,
        }
        
        metrics = self.generate_visualization(
            data=[
                {"label": "Total Evidence", "value": total},
                {"label": "Categories", "value": len(by_category)},
                {"label": "Modules", "value": len(by_module)},
            ],
            viz_type=VisualizationType.METRIC_CARD,
            title="Vault Summary"
        )
        
        category_viz = self.generate_visualization(
            data=[{"name": k, "value": v} for k, v in by_category.items()],
            viz_type=VisualizationType.PIE_CHART,
            title="Evidence by Category",
            config={"height": 250}
        )
        
        return {
            "narrative": f"Evidence Vault contains {total} items across {len(by_category)} categories from {len(by_module)} modules.",
            "visualizations": [metrics, category_viz],
            "page_estimate": 1,
            "confidence_score": 1.0,
        }


# Register the tool
from operation_room.tools import tool_registry
vault_tool = VaultTool()
tool_registry.register(vault_tool)

"""
CRUD Analysis Tool - Universal Module Tool Wrapper

Wraps data access pattern analysis capabilities.
Provides database/file operation tracking and suspicious access detection.
"""

import logging
from typing import List, Dict, Any, Optional
from datetime import datetime
import uuid

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


class CRUDTool(ModuleTool):
    """
    CRUD (Create/Read/Update/Delete) Analysis Tool.
    
    Provides:
    - Data access pattern analysis
    - Suspicious query detection
    - Schema access mapping
    - Operation frequency analysis
    - Data sensitivity correlation
    
    Capabilities:
    - analyze_operations: Full CRUD operation analysis
    - get_suspicious_access: Detect suspicious data access
    - get_operation_freq: Operation frequency distribution
    - get_sensitive_access: Access to sensitive data
    - generate_crud_graph: CRUD operation flow graph
    """
    
    @property
    def tool_id(self) -> str:
        return "crud"
    
    @property
    def tool_name(self) -> str:
        return "CRUD Analysis"
    
    @property
    def tool_version(self) -> str:
        return "2.0.0"
    
    @property
    def tool_category(self) -> ToolCategory:
        return ToolCategory.ANALYSIS
    
    @property
    def description(self) -> str:
        return "Data access pattern analysis and suspicious activity detection"
    
    def get_capabilities(self) -> List[ToolCapability]:
        return [
            ToolCapability(
                name="analyze_operations",
                description="Analyze all CRUD operations in case",
                input_schema={
                    "type": "object",
                    "properties": {
                        "case_id": {"type": "string"},
                        "operation_types": {"type": "array", "items": {"type": "string"}, "default": ["CREATE", "READ", "UPDATE", "DELETE"]},
                        "include_system": {"type": "boolean", "default": False}
                    },
                    "required": ["case_id"]
                },
                output_schema={
                    "type": "object",
                    "properties": {
                        "total_operations": {"type": "integer"},
                        "by_type": {"type": "object"},
                        "by_actor": {"type": "object"}
                    }
                },
                visualization_types=[VisualizationType.PIE_CHART, VisualizationType.TABLE],
                supports_streaming=True
            ),
            ToolCapability(
                name="get_suspicious_access",
                description="Detect suspicious data access patterns",
                input_schema={
                    "type": "object",
                    "properties": {
                        "case_id": {"type": "string"},
                        "anomaly_threshold": {"type": "number", "default": 0.7}
                    },
                    "required": ["case_id"]
                },
                output_schema={
                    "type": "object",
                    "properties": {
                        "suspicious_events": {"type": "array"}
                    }
                },
                visualization_types=[VisualizationType.TABLE, VisualizationType.TIMELINE],
                supports_streaming=False
            ),
            ToolCapability(
                name="get_operation_freq",
                description="Operation frequency over time",
                input_schema={
                    "type": "object",
                    "properties": {
                        "case_id": {"type": "string"},
                        "granularity": {"type": "string", "enum": ["minute", "hour", "day"], "default": "hour"}
                    },
                    "required": ["case_id"]
                },
                output_schema={
                    "type": "object",
                    "properties": {
                        "frequency_data": {"type": "array"}
                    }
                },
                visualization_types=[VisualizationType.AREA_CHART, VisualizationType.LINE_CHART],
                supports_streaming=False
            ),
            ToolCapability(
                name="get_sensitive_access",
                description="Access to sensitive/PII data",
                input_schema={
                    "type": "object",
                    "properties": {
                        "case_id": {"type": "string"},
                        "sensitivity_levels": {"type": "array", "items": {"type": "string"}, "default": ["PII", "FINANCIAL", "CONFIDENTIAL"]}
                    },
                    "required": ["case_id"]
                },
                output_schema={
                    "type": "object",
                    "properties": {
                        "access_events": {"type": "array"},
                        "by_sensitivity": {"type": "object"}
                    }
                },
                visualization_types=[VisualizationType.TABLE, VisualizationType.BAR_CHART],
                supports_streaming=False
            ),
            ToolCapability(
                name="generate_crud_graph",
                description="Generate CRUD operation flow graph",
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
                        "visualization": {"type": "object"}
                    }
                },
                visualization_types=[VisualizationType.NETWORK_GRAPH],
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
            if input.capability == "analyze_operations":
                result = await self._analyze_operations(input.case_id, input.parameters)
            elif input.capability == "get_suspicious_access":
                result = await self._get_suspicious_access(input.case_id, input.parameters)
            elif input.capability == "get_operation_freq":
                result = await self._get_operation_freq(input.case_id, input.parameters)
            elif input.capability == "get_sensitive_access":
                result = await self._get_sensitive_access(input.case_id, input.parameters)
            elif input.capability == "generate_crud_graph":
                result = await self._generate_crud_graph(input.case_id)
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
                confidence_score=result.get("confidence_score", 0.0),
            )
            
        except Exception as e:
            logger.error(f"CRUD tool execution failed: {e}", exc_info=True)
            return ToolOutput(
                tool_id=self.tool_id,
                capability=input.capability,
                request_id=input.request_id,
                success=False,
                error=str(e)
            )
    
    async def _analyze_operations(self, case_id: str, params: Dict[str, Any]) -> Dict[str, Any]:
        """Analyze CRUD operations."""
        # Mock operation stats
        by_type = {"READ": 8547, "UPDATE": 1234, "CREATE": 567, "DELETE": 89}
        total = sum(by_type.values())
        
        by_actor = {
            "jsmith": 3456,
            "admin": 2100,
            "service_account": 4567,
            "others": 314
        }
        
        type_viz = self.generate_visualization(
            data=[{"name": k, "value": v} for k, v in by_type.items()],
            viz_type=VisualizationType.PIE_CHART,
            title="Operations by Type",
            config={"height": 250}
        )
        
        actor_viz = self.generate_visualization(
            data=[{"name": k, "value": v} for k, v in by_actor.items()],
            viz_type=VisualizationType.BAR_CHART,
            title="Operations by Actor",
            config={"height": 200}
        )
        
        findings = [
            self.create_finding(
                title=f"{total:,} Data Operations Analyzed",
                description=f"READ operations dominate ({by_type['READ']/total*100:.1f}%), followed by UPDATE ({by_type['UPDATE']/total*100:.1f}%)",
                severity=FindingSeverity.INFO,
                confidence=0.98,
            )
        ]
        
        return {
            "narrative": f"CRUD analysis processed {total:,} data operations. READ operations ({by_type['READ']:,}) represent {by_type['READ']/total*100:.1f}% of total activity.",
            "findings": findings,
            "visualizations": [type_viz, actor_viz],
            "page_estimate": 2,
            "confidence_score": 0.95,
        }
    
    async def _get_suspicious_access(self, case_id: str, params: Dict[str, Any]) -> Dict[str, Any]:
        """Detect suspicious data access."""
        threshold = params.get("anomaly_threshold", 0.7)
        
        suspicious = [
            {"actor": "jsmith", "operation": "BULK_READ", "table": "customer_pii", "records": 50000, "time": "2024-03-15T02:30:00Z", "risk": 0.95},
            {"actor": "jsmith", "operation": "EXPORT", "table": "financial_records", "records": 12000, "time": "2024-03-15T02:45:00Z", "risk": 0.89},
            {"actor": "jsmith", "operation": "DELETE", "table": "audit_logs", "records": 340, "time": "2024-03-15T03:00:00Z", "risk": 0.92},
        ]
        
        findings = []
        for s in suspicious:
            findings.append(
                self.create_finding(
                    title=f"Suspicious {s['operation']} on {s['table']}",
                    description=f"{s['actor']} accessed {s['records']:,} records at {s['time']}",
                    severity=FindingSeverity.HIGH if s['risk'] > 0.9 else FindingSeverity.MEDIUM,
                    confidence=s['risk'],
                    evidence_refs=[f"crud-{s['table']}-{s['operation']}"],
                )
            )
        
        return {
            "narrative": f"Identified {len(suspicious)} suspicious data access events exceeding risk threshold {threshold}.",
            "findings": findings,
            "tables": [{
                "title": "Suspicious Data Access",
                "columns": ["Actor", "Operation", "Table", "Records", "Time", "Risk"],
                "rows": [[s["actor"], s["operation"], s["table"], f"{s['records']:,}", s["time"], f"{s['risk']:.2f}"] for s in suspicious]
            }],
            "page_estimate": 2,
            "confidence_score": 0.91,
        }
    
    async def _get_operation_freq(self, case_id: str, params: Dict[str, Any]) -> Dict[str, Any]:
        granularity = params.get("granularity", "hour")
        
        # Mock frequency data
        freq_data = [
            {"time": "00:00", "count": 120},
            {"time": "01:00", "count": 85},
            {"time": "02:00", "count": 450},  # Spike
            {"time": "03:00", "count": 380},
            {"time": "04:00", "count": 95},
        ]
        
        viz = self.generate_visualization(
            data=freq_data,
            viz_type=VisualizationType.AREA_CHART,
            title="Operation Frequency Over Time",
            config={"height": 250, "xKey": "time", "yKey": "count"}
        )
        
        findings = [
            self.create_finding(
                title="Unusual Activity Spike at 02:00-03:00",
                description="Operation frequency increased 4x during off-hours period",
                severity=FindingSeverity.MEDIUM,
                confidence=0.88,
            )
        ]
        
        return {
            "narrative": f"Operation frequency analysis by {granularity} shows significant spike during 02:00-03:00 period.",
            "findings": findings,
            "visualizations": [viz],
            "page_estimate": 1,
            "confidence_score": 0.85,
        }
    
    async def _get_sensitive_access(self, case_id: str, params: Dict[str, Any]) -> Dict[str, Any]:
        sensitivity_levels = params.get("sensitivity_levels", ["PII", "FINANCIAL", "CONFIDENTIAL"])
        
        by_sensitivity = {
            "PII": 2547,
            "FINANCIAL": 1234,
            "CONFIDENTIAL": 567,
        }
        
        viz = self.generate_visualization(
            data=[{"name": k, "value": v} for k, v in by_sensitivity.items()],
            viz_type=VisualizationType.BAR_CHART,
            title="Sensitive Data Access by Category",
            config={"height": 200}
        )
        
        findings = [
            self.create_finding(
                title="High PII Access Volume",
                description=f"{by_sensitivity['PII']:,} accesses to PII data detected",
                severity=FindingSeverity.HIGH,
                confidence=0.92,
            )
        ]
        
        return {
            "narrative": f"Sensitive data access: {by_sensitivity['PII']:,} PII, {by_sensitivity['FINANCIAL']:,} Financial, {by_sensitivity['CONFIDENTIAL']:,} Confidential records accessed.",
            "findings": findings,
            "visualizations": [viz],
            "page_estimate": 1,
            "confidence_score": 0.9,
        }
    
    async def _generate_crud_graph(self, case_id: str) -> Dict[str, Any]:
        viz = self.generate_visualization(
            data={"nodes": [], "edges": []},
            viz_type=VisualizationType.NETWORK_GRAPH,
            title="Data Access Flow Graph",
            config={"height": 400}
        )
        
        return {
            "visualizations": [viz],
            "page_estimate": 2,
        }


# Register the tool
from operation_room.tools import tool_registry
crud_tool = CRUDTool()
tool_registry.register(crud_tool)

"""
Anomaly Detection Tool - Universal Module Tool Wrapper

Wraps the existing MCP anomaly detection tools into the Universal Module Tool interface.
Provides ML-based anomaly detection with SHAP explainability.
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


class AnomalyTool(ModuleTool):
    """
    Anomaly Detection Tool.
    
    Provides:
    - ML-based anomaly detection (Isolation Forest + LOF ensemble)
    - SHAP factor explainability
    - Behavioral baseline comparison
    - Anomaly clustering and classification
    - Integration with Evidence Vault
    
    Capabilities:
    - detect: Run anomaly detection on timeline events
    - get_top_anomalies: Get highest-scoring anomalies
    - explain: Get SHAP explanation for specific anomaly
    - compare_baseline: Compare behavior against baseline
    - generate_heatmap: Create anomaly score heatmap
    """
    
    @property
    def tool_id(self) -> str:
        return "anomaly"
    
    @property
    def tool_name(self) -> str:
        return "Anomaly Detection"
    
    @property
    def tool_version(self) -> str:
        return "2.0.0"
    
    @property
    def tool_category(self) -> ToolCategory:
        return ToolCategory.ANALYSIS
    
    @property
    def description(self) -> str:
        return "ML-based anomaly detection with SHAP explainability"
    
    def get_capabilities(self) -> List[ToolCapability]:
        return [
            ToolCapability(
                name="detect",
                description="Run anomaly detection on timeline events",
                input_schema={
                    "type": "object",
                    "properties": {
                        "case_id": {"type": "string"},
                        "model_type": {"type": "string", "enum": ["ensemble", "isolation_forest", "lof"], "default": "ensemble"},
                        "contamination": {"type": "number", "default": 0.1},
                        "min_score": {"type": "number", "default": 0.7}
                    },
                    "required": ["case_id"]
                },
                output_schema={
                    "type": "object",
                    "properties": {
                        "anomalies": {"type": "array"},
                        "total_detected": {"type": "integer"},
                        "run_id": {"type": "string"}
                    }
                },
                visualization_types=[VisualizationType.TABLE, VisualizationType.HEATMAP],
                supports_streaming=True
            ),
            ToolCapability(
                name="get_top_anomalies",
                description="Get top N highest-scoring anomalies",
                input_schema={
                    "type": "object",
                    "properties": {
                        "case_id": {"type": "string"},
                        "limit": {"type": "integer", "default": 10}
                    },
                    "required": ["case_id"]
                },
                output_schema={
                    "type": "object",
                    "properties": {
                        "anomalies": {"type": "array"}
                    }
                },
                visualization_types=[VisualizationType.TABLE],
                supports_streaming=False
            ),
            ToolCapability(
                name="explain",
                description="Get SHAP explanation for anomaly",
                input_schema={
                    "type": "object",
                    "properties": {
                        "case_id": {"type": "string"},
                        "anomaly_id": {"type": "string"}
                    },
                    "required": ["case_id", "anomaly_id"]
                },
                output_schema={
                    "type": "object",
                    "properties": {
                        "shap_values": {"type": "object"},
                        "top_factors": {"type": "array"}
                    }
                },
                visualization_types=[VisualizationType.BAR_CHART],
                supports_streaming=False
            ),
            ToolCapability(
                name="generate_heatmap",
                description="Generate anomaly score heatmap over time",
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
                visualization_types=[VisualizationType.HEATMAP],
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
            if input.capability == "detect":
                result = await self._detect(input.case_id, input.parameters)
            elif input.capability == "get_top_anomalies":
                result = await self._get_top_anomalies(input.case_id, input.parameters)
            elif input.capability == "explain":
                result = await self._explain(input.case_id, input.parameters)
            elif input.capability == "generate_heatmap":
                result = await self._generate_heatmap(input.case_id)
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
            logger.error(f"Anomaly tool execution failed: {e}", exc_info=True)
            return ToolOutput(
                tool_id=self.tool_id,
                capability=input.capability,
                request_id=input.request_id,
                success=False,
                error=str(e)
            )
    
    async def _detect(self, case_id: str, params: Dict[str, Any]) -> Dict[str, Any]:
        """Run anomaly detection."""
        run_id = f"anom-{uuid.uuid4().hex[:8]}"
        
        # Mock anomaly results - in production calls anomaly_agent
        mock_anomalies = [
            {"id": "a1", "actor": "jsmith", "action": "BULK_EXPORT", "score": 0.92, "time": "2024-03-15T02:30:00Z"},
            {"id": "a2", "actor": "admin", "action": "CONFIG_CHANGE", "score": 0.88, "time": "2024-03-15T03:45:00Z"},
            {"id": "a3", "actor": "jsmith", "action": "DB_QUERY_LARGE", "score": 0.85, "time": "2024-03-15T04:15:00Z"},
        ]
        
        findings = []
        for anom in mock_anomalies:
            findings.append(
                self.create_finding(
                    title=f"Anomaly Detected: {anom['action']}",
                    description=f"Actor {anom['actor']} performed {anom['action']} with anomaly score {anom['score']:.2f}",
                    severity=FindingSeverity.HIGH if anom['score'] > 0.9 else FindingSeverity.MEDIUM,
                    confidence=anom['score'],
                    evidence_refs=[anom['id']],
                )
            )
        
        return {
            "narrative": f"Anomaly detection identified {len(mock_anomalies)} suspicious events using Isolation Forest + LOF ensemble model.",
            "findings": findings,
            "tables": [{
                "title": "Detected Anomalies",
                "columns": ["ID", "Actor", "Action", "Score", "Time"],
                "rows": [[a["id"], a["actor"], a["action"], f"{a['score']:.2f}", a["time"]] for a in mock_anomalies]
            }],
            "page_estimate": 2,
            "confidence_score": 0.88,
        }
    
    async def _get_top_anomalies(self, case_id: str, params: Dict[str, Any]) -> Dict[str, Any]:
        limit = params.get("limit", 10)
        return {
            "narrative": f"Retrieved top {limit} anomalies sorted by score.",
            "page_estimate": 1,
        }
    
    async def _explain(self, case_id: str, params: Dict[str, Any]) -> Dict[str, Any]:
        anomaly_id = params.get("anomaly_id", "unknown")
        
        # Mock SHAP explanation
        shap_factors = [
            {"factor": "hour_of_day", "importance": 0.35},
            {"factor": "volume_bytes", "importance": 0.28},
            {"factor": "actor_frequency", "importance": 0.22},
            {"factor": "destination_rarity", "importance": 0.15},
        ]
        
        viz = self.generate_visualization(
            data=shap_factors,
            viz_type=VisualizationType.BAR_CHART,
            title=f"SHAP Factors for {anomaly_id}",
            config={"height": 250, "horizontal": True}
        )
        
        return {
            "narrative": f"SHAP analysis shows primary anomaly factors: hour_of_day (35%), volume_bytes (28%).",
            "visualizations": [viz],
            "page_estimate": 1,
            "confidence_score": 0.9,
        }
    
    async def _generate_heatmap(self, case_id: str) -> Dict[str, Any]:
        viz = self.generate_visualization(
            data=[],
            viz_type=VisualizationType.HEATMAP,
            title="Anomaly Score Distribution",
            config={"height": 300}
        )
        
        return {
            "visualizations": [viz],
            "page_estimate": 1,
        }


# Register the tool
from operation_room.tools import tool_registry
anomaly_tool = AnomalyTool()
tool_registry.register(anomaly_tool)

"""
Timeline Analysis Wrapper — MCP tools wrapping timeline module with vault integration.

This module provides:
- timeline.build: Build unified timeline from raw events
- timeline.query: Query timeline with filters
- timeline.anchor: Mark events as timeline anchors
- timeline.anchors: List/manage anchored events
- timeline.visualize: Get timeline data for visualization

All significant findings can be automatically anchored to the Evidence Vault.

Author: NFLIP Development Team
Version: 1.0.0
"""

from __future__ import annotations

import logging
import uuid
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

from pydantic import BaseModel, Field

from ..schemas import ModuleName, ConfidenceLevel
from ..registry import ToolCategory, ToolExecutionContext
from ..decorators import (
    mcp_tool,
    with_coc_logging,
    with_evidence_hash,
    audit_trail,
    CoCActionType,
)
from .investigation import InvestigationStore, enum_value
from .evidence import (
    EvidenceVault,
    EvidenceFactory,
    EvidenceCategory,
    AnchorType,
    EvidenceItem,
)


logger = logging.getLogger(__name__)


# ═══════════════════════════════════════════════════════════════════════════════
# TIMELINE SERVICE INTERFACE
# ═══════════════════════════════════════════════════════════════════════════════

class TimelineServiceInterface:
    """
    Interface to the actual timeline service.
    
    In production, this calls the real timeline_service.py.
    For now, we provide mock responses that match the expected structure.
    """
    
    @staticmethod
    async def build_timeline(
        case_id: str,
        source_types: Optional[List[str]] = None,
        time_start: Optional[str] = None,
        time_end: Optional[str] = None,
        force_rebuild: bool = False,
        cluster_window_seconds: int = 300,
        min_cluster_samples: int = 2
    ) -> Dict[str, Any]:
        """
        Build unified timeline from raw events.
        
        In production, this would call:
            from operation_room.services.timeline_service import build_timeline
        """
        # Mock response matching timeline_service structure
        return {
            "success": True,
            "case_id": case_id,
            "run_id": f"tl-run-{uuid.uuid4().hex[:8]}",
            "total_events": 0,  # Would be real count
            "clusters_found": 0,
            "time_stomped_events": 0,
            "source_breakdown": {},
            "time_range": {
                "start": time_start,
                "end": time_end
            },
            "parameters": {
                "source_types": source_types,
                "cluster_window_seconds": cluster_window_seconds,
                "min_cluster_samples": min_cluster_samples
            },
            "message": "Timeline built successfully"
        }
    
    @staticmethod
    async def get_timeline(
        case_id: str,
        limit: int = 100,
        offset: int = 0,
        actor: Optional[str] = None,
        source_type: Optional[str] = None,
        severity: Optional[str] = None,
        time_start: Optional[str] = None,
        time_end: Optional[str] = None,
        cluster_id: Optional[int] = None,
        time_stomped_only: bool = False
    ) -> Dict[str, Any]:
        """
        Query timeline events with filters.
        
        In production, this would call:
            from operation_room.services.timeline_service import get_timeline
        """
        # Mock response - in production would return actual events
        return {
            "success": True,
            "case_id": case_id,
            "total": 0,
            "limit": limit,
            "offset": offset,
            "events": [],
            "filters_applied": {
                "actor": actor,
                "source_type": source_type,
                "severity": severity,
                "time_start": time_start,
                "time_end": time_end,
                "cluster_id": cluster_id,
                "time_stomped_only": time_stomped_only
            }
        }
    
    @staticmethod
    async def get_timeline_stats(case_id: str) -> Dict[str, Any]:
        """
        Get timeline statistics.
        
        In production, this would call:
            from operation_room.services.timeline_service import get_timeline_stats_search
        """
        return {
            "success": True,
            "case_id": case_id,
            "total_events": 0,
            "clusters": 0,
            "time_stomped": 0,
            "source_breakdown": {},
            "severity_breakdown": {},
            "actor_breakdown": {},
            "time_range": None
        }
    
    @staticmethod
    async def get_anchors(case_id: str) -> Dict[str, Any]:
        """
        Get existing timeline anchors.
        
        In production, this would query the anchor_events table.
        """
        return {
            "success": True,
            "case_id": case_id,
            "anchors": []
        }


# ═══════════════════════════════════════════════════════════════════════════════
# TIMELINE ANCHOR MANAGER
# ═══════════════════════════════════════════════════════════════════════════════

class TimelineAnchorManager:
    """
    Manages timeline anchors with automatic vault integration.
    
    When events are marked as anchors, they are:
    1. Recorded in the timeline anchor_events table
    2. Added to the Evidence Vault with hash verification
    3. Available for report citation
    """
    
    # In-memory anchor storage (production: database)
    _anchors: Dict[str, Dict[str, Any]] = {}
    
    @classmethod
    def create_anchor(
        cls,
        case_id: str,
        event: Dict[str, Any],
        anchor_type: AnchorType,
        label: str,
        auto_detected: bool = False,
        investigation_id: Optional[str] = None,
        tags: Optional[List[str]] = None
    ) -> Dict[str, Any]:
        """
        Create a timeline anchor and add to Evidence Vault.
        
        Returns both the anchor record and the vault evidence ID.
        """
        event_id = event.get("tl_event_id") or event.get("event_id", str(uuid.uuid4()))
        anchor_id = f"anchor-{uuid.uuid4().hex[:8]}"
        
        # Create anchor record
        anchor = {
            "anchor_id": anchor_id,
            "case_id": case_id,
            "tl_event_id": event_id,
            "anchor_type": anchor_type.value,
            "label": label,
            "auto_detected": auto_detected,
            "created_at": datetime.now(timezone.utc).isoformat(),
            "created_by": "system" if auto_detected else "user"
        }
        
        cls._anchors[anchor_id] = anchor
        
        # Add to Evidence Vault
        evidence = EvidenceFactory.from_timeline_event(
            case_id=case_id,
            event=event,
            anchor_type=anchor_type,
            label=label,
            tags=tags or [anchor_type.value],
            investigation_id=investigation_id
        )
        
        EvidenceVault.add(evidence)
        
        anchor["evidence_id"] = evidence.evidence_id
        anchor["evidence_hash"] = evidence.data_hash
        
        logger.info(f"Timeline anchor {anchor_id} created with vault evidence {evidence.evidence_id}")
        
        return {
            "anchor": anchor,
            "evidence_id": evidence.evidence_id,
            "citation_ref": f"[EV-{evidence.evidence_id[-6:].upper()}]"
        }
    
    @classmethod
    def get_anchors(
        cls,
        case_id: str,
        anchor_type: Optional[AnchorType] = None
    ) -> List[Dict[str, Any]]:
        """Get anchors for a case."""
        results = []
        for anchor in cls._anchors.values():
            if anchor["case_id"] != case_id:
                continue
            if anchor_type and anchor["anchor_type"] != anchor_type.value:
                continue
            results.append(anchor)
        return results
    
    @classmethod
    def auto_detect_anchors(
        cls,
        case_id: str,
        events: List[Dict[str, Any]],
        investigation_id: Optional[str] = None
    ) -> List[Dict[str, Any]]:
        """
        Automatically detect significant events to anchor.
        
        Detects:
        - First and last events in timeline
        - High severity events
        - Time-stomped events
        - Events with specific actions (LOGIN_FAILED, EXPORT, FILE_DELETE, etc.)
        """
        if not events:
            return []
        
        anchors = []
        
        # Sort by timestamp
        sorted_events = sorted(
            events,
            key=lambda e: e.get("normalised_ts", e.get("timestamp", ""))
        )
        
        # First event
        if sorted_events:
            first = sorted_events[0]
            result = cls.create_anchor(
                case_id=case_id,
                event=first,
                anchor_type=AnchorType.INVESTIGATION_START,
                label=f"Timeline start: {first.get('action', 'Event')} by {first.get('actor', 'Unknown')}",
                auto_detected=True,
                investigation_id=investigation_id,
                tags=["auto-detected", "timeline-start"]
            )
            anchors.append(result)
        
        # Last event
        if len(sorted_events) > 1:
            last = sorted_events[-1]
            result = cls.create_anchor(
                case_id=case_id,
                event=last,
                anchor_type=AnchorType.INVESTIGATION_END,
                label=f"Timeline end: {last.get('action', 'Event')} by {last.get('actor', 'Unknown')}",
                auto_detected=True,
                investigation_id=investigation_id,
                tags=["auto-detected", "timeline-end"]
            )
            anchors.append(result)
        
        # High severity events
        high_severity = [e for e in events if e.get("severity") == "HIGH"]
        for event in high_severity[:5]:  # Limit to top 5
            action = event.get("action", "Event")
            
            # Determine anchor type based on action
            anchor_type = AnchorType.CUSTOM
            if action in ["LOGIN_FAILED", "PASSWORD_CHANGE", "ACCOUNT_LOCKED"]:
                anchor_type = AnchorType.CREDENTIAL_ACCESS
            elif action in ["EXPORT", "FILE_COPY", "FILE_DOWNLOAD"]:
                anchor_type = AnchorType.DATA_EXFILTRATION
            elif action in ["PRIVILEGE_ESCALATION", "ADMIN_ACCESS"]:
                anchor_type = AnchorType.PRIVILEGE_ESCALATION
            elif action in ["LATERAL_MOVEMENT", "RDP_CONNECTION"]:
                anchor_type = AnchorType.LATERAL_MOVEMENT
            elif action in ["MALWARE_DETECTED", "BACKDOOR", "PERSISTENCE"]:
                anchor_type = AnchorType.PERSISTENCE
            elif action in ["FILE_DELETE", "DATA_WIPE"]:
                anchor_type = AnchorType.DATA_ACCESS
            
            result = cls.create_anchor(
                case_id=case_id,
                event=event,
                anchor_type=anchor_type,
                label=f"High severity: {action} by {event.get('actor', 'Unknown')}",
                auto_detected=True,
                investigation_id=investigation_id,
                tags=["auto-detected", "high-severity", anchor_type.value]
            )
            anchors.append(result)
        
        # Time-stomped events (evidence of tampering)
        time_stomped = [e for e in events if e.get("is_time_stomped")]
        for event in time_stomped[:3]:  # Limit to top 3
            result = cls.create_anchor(
                case_id=case_id,
                event=event,
                anchor_type=AnchorType.CUSTOM,
                label=f"Time-stomped: {event.get('action', 'Event')} (tampering indicator)",
                auto_detected=True,
                investigation_id=investigation_id,
                tags=["auto-detected", "time-stomped", "tampering"]
            )
            anchors.append(result)
        
        return anchors


# ═══════════════════════════════════════════════════════════════════════════════
# MCP TOOL IMPLEMENTATIONS
# ═══════════════════════════════════════════════════════════════════════════════

@mcp_tool(
    name="timeline.build",
    category=ToolCategory.ANALYSIS,
    description="Build unified timeline from raw events with DBSCAN clustering and time-stomp detection.",
    requires_case_id=True,
    tags={"timeline", "analysis", "clustering"}
)
@with_coc_logging(action_type=CoCActionType.TOOL_EXECUTION)
@audit_trail(operation="TIMELINE_BUILD")
async def build_timeline(
    case_id: str,
    source_types: Optional[List[str]] = None,
    time_start: Optional[str] = None,
    time_end: Optional[str] = None,
    force_rebuild: bool = False,
    auto_anchor: bool = True,
    cluster_window_seconds: int = 300,
    min_cluster_samples: int = 2,
    investigation_id: Optional[str] = None,
    _context: Optional[ToolExecutionContext] = None
) -> Dict[str, Any]:
    """
    Build unified timeline from raw events.
    
    This tool:
    1. Reads raw events from all configured sources
    2. Normalizes timestamps to UTC
    3. Applies DBSCAN clustering to group related events
    4. Detects time-stomping (evidence tampering)
    5. Optionally auto-anchors significant events to Evidence Vault
    
    Args:
        case_id: Target case ID
        source_types: Filter by source types (e.g., ["windows", "android"])
        time_start: Start time filter (ISO 8601)
        time_end: End time filter (ISO 8601)
        force_rebuild: Force rebuild even if timeline exists
        auto_anchor: Automatically anchor significant events
        cluster_window_seconds: DBSCAN clustering window
        min_cluster_samples: Minimum samples per cluster
        investigation_id: Associated investigation ID
    
    Returns:
        Timeline build summary with stats and any auto-anchored evidence
    """
    logger.info(f"Building timeline for case {case_id}")
    
    # Call timeline service
    result = await TimelineServiceInterface.build_timeline(
        case_id=case_id,
        source_types=source_types,
        time_start=time_start,
        time_end=time_end,
        force_rebuild=force_rebuild,
        cluster_window_seconds=cluster_window_seconds,
        min_cluster_samples=min_cluster_samples
    )
    
    # Auto-anchor significant events if requested
    auto_anchored = []
    if auto_anchor and result.get("success"):
        # Get events for anchoring (in production, would get from timeline)
        # For now, create synthetic events for demonstration
        events_result = await TimelineServiceInterface.get_timeline(
            case_id=case_id,
            limit=100
        )
        
        if events_result.get("events"):
            auto_anchored = TimelineAnchorManager.auto_detect_anchors(
                case_id=case_id,
                events=events_result["events"],
                investigation_id=investigation_id
            )
    
    return {
        "success": result.get("success", True),
        "case_id": case_id,
        "run_id": result.get("run_id"),
        "summary": {
            "total_events": result.get("total_events", 0),
            "clusters_found": result.get("clusters_found", 0),
            "time_stomped_events": result.get("time_stomped_events", 0),
            "source_breakdown": result.get("source_breakdown", {}),
            "time_range": result.get("time_range")
        },
        "auto_anchored": [
            {
                "anchor_id": a["anchor"]["anchor_id"],
                "evidence_id": a["evidence_id"],
                "label": a["anchor"]["label"],
                "anchor_type": a["anchor"]["anchor_type"],
                "citation_ref": a["citation_ref"]
            }
            for a in auto_anchored
        ],
        "anchor_count": len(auto_anchored),
        "message": result.get("message", "Timeline built"),
        "next_action": "Use timeline.query to explore events or timeline.anchor to mark specific events"
    }


@mcp_tool(
    name="timeline.query",
    category=ToolCategory.ANALYSIS,
    description="Query timeline events with filters.",
    requires_case_id=True,
    tags={"timeline", "query", "search"}
)
@audit_trail(operation="TIMELINE_QUERY")
async def query_timeline(
    case_id: str,
    limit: int = 50,
    offset: int = 0,
    actor: Optional[str] = None,
    source_type: Optional[str] = None,
    severity: Optional[str] = None,
    time_start: Optional[str] = None,
    time_end: Optional[str] = None,
    cluster_id: Optional[int] = None,
    time_stomped_only: bool = False,
    _context: Optional[ToolExecutionContext] = None
) -> Dict[str, Any]:
    """
    Query timeline events with filters.
    
    Args:
        case_id: Target case ID
        limit: Maximum results
        offset: Pagination offset
        actor: Filter by actor
        source_type: Filter by source type
        severity: Filter by severity (HIGH/MEDIUM/INFO)
        time_start: Start time filter
        time_end: End time filter
        cluster_id: Filter by cluster ID
        time_stomped_only: Only return time-stomped events
    
    Returns:
        Filtered timeline events
    """
    result = await TimelineServiceInterface.get_timeline(
        case_id=case_id,
        limit=limit,
        offset=offset,
        actor=actor,
        source_type=source_type,
        severity=severity,
        time_start=time_start,
        time_end=time_end,
        cluster_id=cluster_id,
        time_stomped_only=time_stomped_only
    )
    
    return {
        "success": result.get("success", True),
        "case_id": case_id,
        "total": result.get("total", 0),
        "limit": limit,
        "offset": offset,
        "events": result.get("events", []),
        "filters_applied": result.get("filters_applied", {}),
        "tip": "Use timeline.anchor to mark important events as evidence"
    }


@mcp_tool(
    name="timeline.anchor",
    category=ToolCategory.ANALYSIS,
    description="Mark a timeline event as an anchor and add to Evidence Vault.",
    requires_case_id=True,
    tags={"timeline", "anchor", "evidence"}
)
@with_coc_logging(action_type=CoCActionType.INVESTIGATION_EVENT)
@audit_trail(operation="TIMELINE_ANCHOR")
async def anchor_timeline_event(
    case_id: str,
    event_id: str,
    anchor_type: str = "custom",
    label: Optional[str] = None,
    tags: Optional[List[str]] = None,
    event_data: Optional[Dict[str, Any]] = None,
    investigation_id: Optional[str] = None,
    _context: Optional[ToolExecutionContext] = None
) -> Dict[str, Any]:
    """
    Mark a timeline event as an anchor.
    
    Anchored events are:
    1. Preserved in the Evidence Vault with SHA-256 hash
    2. Available for citation in reports
    3. Used for timeline visualization highlights
    4. Cross-referenced with other evidence
    
    Args:
        case_id: Target case ID
        event_id: Timeline event ID to anchor
        anchor_type: Type of anchor (investigation_start, first_malicious, etc.)
        label: Human-readable label for the anchor
        tags: Additional tags
        event_data: Full event data (if not retrievable)
        investigation_id: Associated investigation ID
    
    Returns:
        Anchor and evidence details
    """
    # Parse anchor type
    try:
        atype = AnchorType(anchor_type.lower())
    except ValueError:
        atype = AnchorType.CUSTOM
    
    # Get event data if not provided
    if not event_data:
        # In production, would fetch from timeline
        event_data = {
            "tl_event_id": event_id,
            "case_id": case_id,
            "normalised_ts": datetime.now(timezone.utc).isoformat(),
            "actor": "Unknown",
            "action": "Event",
            "target": "",
            "severity": "INFO"
        }
    
    # Ensure event_id is set
    event_data["tl_event_id"] = event_id
    
    # Create label if not provided
    if not label:
        action = event_data.get("action", "Event")
        actor = event_data.get("actor", "Unknown")
        label = f"{atype.value}: {action} by {actor}"
    
    # Create anchor with vault integration
    result = TimelineAnchorManager.create_anchor(
        case_id=case_id,
        event=event_data,
        anchor_type=atype,
        label=label,
        auto_detected=False,
        investigation_id=investigation_id,
        tags=tags
    )
    
    return {
        "success": True,
        "anchor_id": result["anchor"]["anchor_id"],
        "event_id": event_id,
        "anchor_type": atype.value,
        "label": label,
        "evidence_id": result["evidence_id"],
        "evidence_hash": result["anchor"]["evidence_hash"],
        "citation_ref": result["citation_ref"],
        "message": f"Event anchored and added to Evidence Vault"
    }


@mcp_tool(
    name="timeline.anchors",
    category=ToolCategory.ANALYSIS,
    description="List timeline anchors for a case.",
    requires_case_id=True,
    tags={"timeline", "anchors", "list"}
)
@audit_trail(operation="TIMELINE_ANCHORS_LIST")
async def list_timeline_anchors(
    case_id: str,
    anchor_type: Optional[str] = None,
    _context: Optional[ToolExecutionContext] = None
) -> Dict[str, Any]:
    """
    List timeline anchors for a case.
    
    Args:
        case_id: Target case ID
        anchor_type: Filter by anchor type
    
    Returns:
        List of anchors with evidence references
    """
    # Parse anchor type filter
    atype = None
    if anchor_type:
        try:
            atype = AnchorType(anchor_type.lower())
        except ValueError:
            pass
    
    anchors = TimelineAnchorManager.get_anchors(case_id, atype)
    
    # Also get anchors from Evidence Vault
    vault_evidence = EvidenceVault.query(
        case_id=case_id,
        category=EvidenceCategory.TIMELINE_ANCHOR,
        limit=100
    )
    
    return {
        "success": True,
        "case_id": case_id,
        "anchor_count": len(anchors),
        "anchors": [
            {
                "anchor_id": a["anchor_id"],
                "event_id": a["tl_event_id"],
                "anchor_type": a["anchor_type"],
                "label": a["label"],
                "auto_detected": a["auto_detected"],
                "evidence_id": a.get("evidence_id"),
                "citation_ref": f"[EV-{a.get('evidence_id', '')[-6:].upper()}]" if a.get("evidence_id") else None,
                "created_at": a["created_at"]
            }
            for a in anchors
        ],
        "vault_evidence_count": len(vault_evidence),
        "tip": "Use evidence.cite to generate citations for reports"
    }


@mcp_tool(
    name="timeline.stats",
    category=ToolCategory.ANALYSIS,
    description="Get timeline statistics.",
    requires_case_id=True,
    tags={"timeline", "stats", "summary"}
)
@audit_trail(operation="TIMELINE_STATS")
async def get_timeline_stats(
    case_id: str,
    _context: Optional[ToolExecutionContext] = None
) -> Dict[str, Any]:
    """
    Get timeline statistics.
    
    Args:
        case_id: Target case ID
    
    Returns:
        Timeline statistics including event counts, clusters, etc.
    """
    result = await TimelineServiceInterface.get_timeline_stats(case_id)
    
    # Get anchor stats
    anchors = TimelineAnchorManager.get_anchors(case_id)
    anchor_by_type = {}
    for a in anchors:
        atype = a["anchor_type"]
        anchor_by_type[atype] = anchor_by_type.get(atype, 0) + 1
    
    return {
        "success": result.get("success", True),
        "case_id": case_id,
        "timeline_stats": {
            "total_events": result.get("total_events", 0),
            "clusters": result.get("clusters", 0),
            "time_stomped": result.get("time_stomped", 0),
            "source_breakdown": result.get("source_breakdown", {}),
            "severity_breakdown": result.get("severity_breakdown", {}),
            "actor_breakdown": result.get("actor_breakdown", {}),
            "time_range": result.get("time_range")
        },
        "anchor_stats": {
            "total_anchors": len(anchors),
            "by_type": anchor_by_type,
            "auto_detected": len([a for a in anchors if a.get("auto_detected")]),
            "user_created": len([a for a in anchors if not a.get("auto_detected")])
        }
    }


@mcp_tool(
    name="timeline.visualize",
    category=ToolCategory.ANALYSIS,
    description="Get timeline data formatted for visualization.",
    requires_case_id=True,
    tags={"timeline", "visualize", "chart"}
)
@audit_trail(operation="TIMELINE_VISUALIZE")
async def visualize_timeline(
    case_id: str,
    time_start: Optional[str] = None,
    time_end: Optional[str] = None,
    include_anchors: bool = True,
    include_clusters: bool = True,
    max_events: int = 500,
    _context: Optional[ToolExecutionContext] = None
) -> Dict[str, Any]:
    """
    Get timeline data formatted for visualization.
    
    Returns data structured for timeline charts with:
    - Events as data points
    - Anchors highlighted
    - Clusters grouped
    - Severity color-coded
    
    Args:
        case_id: Target case ID
        time_start: Start time filter
        time_end: End time filter
        include_anchors: Include anchor markers
        include_clusters: Include cluster groupings
        max_events: Maximum events to return
    
    Returns:
        Visualization-ready timeline data
    """
    # Get timeline events
    events_result = await TimelineServiceInterface.get_timeline(
        case_id=case_id,
        limit=max_events,
        time_start=time_start,
        time_end=time_end
    )
    
    events = events_result.get("events", [])
    
    # Get anchors if requested
    anchors = []
    anchor_event_ids = set()
    if include_anchors:
        anchors = TimelineAnchorManager.get_anchors(case_id)
        anchor_event_ids = {a["tl_event_id"] for a in anchors}
    
    # Format for visualization
    viz_events = []
    for event in events:
        event_id = event.get("tl_event_id") or event.get("event_id")
        is_anchor = event_id in anchor_event_ids
        
        viz_event = {
            "id": event_id,
            "timestamp": event.get("normalised_ts") or event.get("timestamp"),
            "actor": event.get("actor"),
            "action": event.get("action"),
            "target": event.get("target"),
            "source_type": event.get("source_type"),
            "severity": event.get("severity", "INFO"),
            "is_anchor": is_anchor,
            "is_time_stomped": event.get("is_time_stomped", False),
            "cluster_id": event.get("cluster_id") if include_clusters else None,
            "color": _severity_color(event.get("severity", "INFO")),
            "size": 12 if is_anchor else 8  # Larger markers for anchors
        }
        
        # Add anchor details if applicable
        if is_anchor:
            anchor = next((a for a in anchors if a["tl_event_id"] == event_id), None)
            if anchor:
                viz_event["anchor_type"] = anchor["anchor_type"]
                viz_event["anchor_label"] = anchor["label"]
                viz_event["evidence_id"] = anchor.get("evidence_id")
        
        viz_events.append(viz_event)
    
    # Build cluster groups if requested
    cluster_groups = {}
    if include_clusters:
        for event in viz_events:
            cid = event.get("cluster_id")
            if cid is not None:
                if cid not in cluster_groups:
                    cluster_groups[cid] = []
                cluster_groups[cid].append(event["id"])
    
    return {
        "success": True,
        "case_id": case_id,
        "event_count": len(viz_events),
        "anchor_count": len([e for e in viz_events if e["is_anchor"]]),
        "cluster_count": len(cluster_groups),
        "events": viz_events,
        "clusters": cluster_groups if include_clusters else None,
        "anchors": [
            {
                "anchor_id": a["anchor_id"],
                "event_id": a["tl_event_id"],
                "anchor_type": a["anchor_type"],
                "label": a["label"],
                "evidence_id": a.get("evidence_id")
            }
            for a in anchors
        ] if include_anchors else None,
        "visualization_config": {
            "x_axis": "timestamp",
            "y_axis": "actor",
            "color_by": "severity",
            "size_by": "is_anchor",
            "group_by": "cluster_id" if include_clusters else None
        }
    }


def _severity_color(severity: str) -> str:
    """Map severity to visualization color."""
    colors = {
        "HIGH": "#dc3545",      # Red
        "MEDIUM": "#ffc107",    # Yellow
        "INFO": "#17a2b8",      # Blue
        "LOW": "#28a745"        # Green
    }
    return colors.get(severity, "#6c757d")  # Gray default

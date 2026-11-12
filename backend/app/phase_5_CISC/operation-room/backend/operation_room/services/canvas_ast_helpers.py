"""
Canvas AST Helpers.

Extracted from auto_report_builder.py per the pipeline deprecation plan.
These utility functions build TipTap/Canvas AST nodes for the Report Studio
UI. They are used by both the legacy report builder and the new canonical
pipeline for rendering visual components on the A4 canvas.

NOTE: The chart builders include a fallback ladder (Phase 5):
  - If data exceeds visual capacity (>20 bars), downgrade to Top-10 table
  - If table still overflows, downgrade to text summary paragraph
"""

import uuid
from typing import Any, Dict, List, Optional


# ═══════════════════════════════════════════════════════════════════════════════
# TIPTAP AST NODE BUILDERS
# ═══════════════════════════════════════════════════════════════════════════════

def build_heading(text: str, level: int = 1) -> Dict:
    """Build TipTap heading node."""
    return {
        "type": "heading",
        "attrs": {"level": level},
        "content": [{"type": "text", "text": text}]
    }


def build_paragraph(text: str) -> Dict:
    """Build TipTap paragraph node."""
    return {
        "type": "paragraph",
        "content": [{"type": "text", "text": text}]
    }


def build_bullet_list(items: List[str]) -> Dict:
    """Build TipTap bullet list node."""
    return {
        "type": "bulletList",
        "content": [
            {
                "type": "listItem",
                "content": [{"type": "paragraph", "content": [{"type": "text", "text": item}]}]
            }
            for item in items
        ]
    }


def build_table(headers: List[str], rows: List[List[str]]) -> Dict:
    """Build TipTap table node."""
    header_row = {
        "type": "tableRow",
        "content": [
            {"type": "tableHeader", "content": [{"type": "paragraph", "content": [{"type": "text", "text": h}]}]}
            for h in headers
        ]
    }

    data_rows = [
        {
            "type": "tableRow",
            "content": [
                {"type": "tableCell", "content": [{"type": "paragraph", "content": [{"type": "text", "text": str(cell)}]}]}
                for cell in row
            ]
        }
        for row in rows
    ]

    return {
        "type": "table",
        "content": [header_row] + data_rows
    }


def build_horizontal_rule() -> Dict:
    """Build TipTap horizontal rule."""
    return {"type": "horizontalRule"}


# ═══════════════════════════════════════════════════════════════════════════════
# CHART COMPONENT BUILDERS (with Phase 5 Fallback Ladder)
# ═══════════════════════════════════════════════════════════════════════════════

# Threshold beyond which a bar chart becomes illegible on A4
_MAX_CHART_BARS = 20
_MAX_TABLE_ROWS = 40


def build_actor_chart(actors: List[Dict], max_bars: int = _MAX_CHART_BARS) -> Dict:
    """
    Build actor activity bar chart component for canvas.

    Fallback Ladder (Phase 5):
      - >max_bars actors → downgrade to Top-10 table
      - >_MAX_TABLE_ROWS actors → downgrade to text summary
    """
    if len(actors) > _MAX_TABLE_ROWS:
        # Fallback Level 2: Text summary
        top_actor = actors[0] if actors else {}
        return build_paragraph(
            f"{len(actors)} actors were identified. "
            f"Primary actor: {top_actor.get('name', top_actor.get('actor', 'N/A'))} "
            f"({top_actor.get('count', top_actor.get('event_count', 0))} events)."
        )

    if len(actors) > max_bars:
        # Fallback Level 1: Top-10 table
        headers = ["Actor", "Events"]
        rows = [
            [a.get("name", a.get("actor", "")), str(a.get("count", a.get("event_count", 0)))]
            for a in actors[:10]
        ]
        return build_table(headers, rows)

    return {
        "type": "component",
        "attrs": {
            "moduleId": "actor_analysis",
            "componentType": "chart",
            "chartType": "bar",
        },
        "data": {
            "type": "chart",
            "chartType": "bar",
            "module": "actor_analysis",
            "componentId": f"actor_chart_{uuid.uuid4().hex[:8]}",
            "title": "Actor Activity Distribution",
            "config": {"indexAxis": "y", "responsive": True},
            "data": {
                "labels": [a.get('name', a.get('actor', '')) for a in actors[:max_bars]],
                "datasets": [{
                    "label": "Events",
                    "data": [a.get('count', a.get('event_count', 0)) for a in actors[:max_bars]],
                    "backgroundColor": ["#3b82f6", "#22c55e", "#f59e0b", "#ef4444",
                                        "#8b5cf6", "#06b6d4", "#ec4899", "#84cc16"] * 3
                }]
            }
        }
    }


def build_severity_pie(severity: List[Dict]) -> Dict:
    """Build severity distribution pie chart component."""
    severity_colors = {
        "CRITICAL": "#ef4444",
        "HIGH": "#f97316",
        "MEDIUM": "#f59e0b",
        "LOW": "#22c55e",
        "INFO": "#06b6d4"
    }

    labels = [s.get('level', s.get('severity', '')) for s in severity]

    return {
        "type": "component",
        "attrs": {
            "moduleId": "severity_analysis",
            "componentType": "chart",
            "chartType": "pie",
        },
        "data": {
            "type": "chart",
            "chartType": "pie",
            "module": "severity_analysis",
            "componentId": f"severity_pie_{uuid.uuid4().hex[:8]}",
            "title": "Severity Distribution",
            "data": {
                "labels": labels,
                "datasets": [{
                    "data": [s.get('count', 0) for s in severity],
                    "backgroundColor": [severity_colors.get(l, "#6366f1") for l in labels]
                }]
            }
        }
    }


def build_timeline_area(hourly_data: List[Dict]) -> Dict:
    """Build timeline area chart component with fallback."""
    if len(hourly_data) > _MAX_TABLE_ROWS:
        # Fallback: text summary
        total = sum(h.get("count", 0) for h in hourly_data)
        peak = max(hourly_data, key=lambda h: h.get("count", 0)) if hourly_data else {}
        return build_paragraph(
            f"Activity spans {len(hourly_data)} time buckets with {total} total events. "
            f"Peak activity at hour {peak.get('hour', 'N/A')} ({peak.get('count', 0)} events)."
        )

    return {
        "type": "component",
        "attrs": {
            "moduleId": "timeline",
            "componentType": "chart",
            "chartType": "area",
        },
        "data": {
            "type": "chart",
            "chartType": "line",
            "module": "timeline",
            "componentId": f"timeline_area_{uuid.uuid4().hex[:8]}",
            "title": "Activity Over Time",
            "config": {"fill": True, "tension": 0.4},
            "data": {
                "labels": [f"{h.get('hour', 0):02d}:00" for h in hourly_data],
                "datasets": [{
                    "label": "Events",
                    "data": [h.get('count', 0) for h in hourly_data],
                    "backgroundColor": "rgba(59, 130, 246, 0.3)",
                    "borderColor": "#3b82f6",
                    "fill": True
                }]
            }
        }
    }


def build_feature_importance(features: Optional[List[Dict]] = None) -> Dict:
    """Build SHAP feature importance component."""
    if features is None:
        features = [
            {"feature": "severity_numeric", "importance": 0.458, "shap_value": 23.460, "direction": "positive"},
            {"feature": "hour_of_day", "importance": 0.293, "shap_value": 15.005, "direction": "positive"},
            {"feature": "target_length", "importance": 0.104, "shap_value": 5.322, "direction": "positive"},
            {"feature": "day_of_week", "importance": 0.098, "shap_value": 5.040, "direction": "positive"},
            {"feature": "actor_frequency", "importance": 0.023, "shap_value": 1.200, "direction": "positive"},
            {"feature": "source_frequency", "importance": 0.022, "shap_value": 1.120, "direction": "positive"},
        ]

    return {
        "type": "component",
        "attrs": {
            "moduleId": "anomaly",
            "componentType": "feature_importance",
        },
        "data": {
            "type": "feature_importance",
            "module": "anomaly",
            "componentId": f"shap_{uuid.uuid4().hex[:8]}",
            "title": "SHAP Feature Importance",
            "prediction": 0.433,
            "features": features
        }
    }


def build_metrics_grid(metrics: Dict) -> Dict:
    """Build key metrics grid component."""
    return {
        "type": "component",
        "attrs": {
            "moduleId": "summary",
            "componentType": "metric_grid",
        },
        "data": {
            "type": "metric_grid",
            "module": "summary",
            "componentId": f"metrics_{uuid.uuid4().hex[:8]}",
            "title": "Key Investigation Metrics",
            "metrics": [
                {"label": "Total Events", "value": metrics.get("total_events", 0), "icon": "\U0001f4ca", "color": "#3b82f6"},
                {"label": "Anomalies", "value": metrics.get("anomalies", 0), "icon": "\u26a0\ufe0f", "color": "#ef4444"},
                {"label": "Actors", "value": metrics.get("actors", 0), "icon": "\U0001f464", "color": "#8b5cf6"},
                {"label": "Sources", "value": metrics.get("sources", 0), "icon": "\U0001f5a5\ufe0f", "color": "#22c55e"},
                {"label": "Risk Level", "value": metrics.get("risk_level", "MEDIUM"), "icon": "\U0001f3af", "color": "#f59e0b"},
            ]
        }
    }


# ═══════════════════════════════════════════════════════════════════════════════
# LAYOUT VALIDATOR (Phase 5 — PDF Visual Integrity)
# ═══════════════════════════════════════════════════════════════════════════════

class LayoutValidator:
    """
    Validates and auto-corrects component AST nodes to ensure they fit
    within ReportLab A4 page boundaries.

    The fallback ladder:
      1. Chart → Top-N Table (if bars > threshold)
      2. Table → Text Summary (if rows still overflow Y-axis)
    """

    A4_HEIGHT_MM = 297
    A4_WIDTH_MM = 210
    MARGIN_MM = 20
    USABLE_HEIGHT_MM = A4_HEIGHT_MM - 2 * MARGIN_MM  # 257mm
    ROW_HEIGHT_MM = 6  # Approximate row height in table
    CHART_HEIGHT_MM = 80  # Default chart height
    MIN_REMAINING_MM = 30  # Minimum space before triggering fallback

    def validate_component(
        self,
        component: Dict,
        remaining_height_mm: float = USABLE_HEIGHT_MM,
    ) -> Dict:
        """
        Validate a component AST node and downgrade if needed.

        Args:
            component: The AST component dict
            remaining_height_mm: Available vertical space on current page

        Returns:
            Original or downgraded component
        """
        data = component.get("data", {})
        component_type = data.get("type", "")

        if component_type == "chart":
            return self._validate_chart(component, data, remaining_height_mm)
        elif component_type == "metric_grid":
            return component  # Metric grids are compact, always fit
        elif component_type == "feature_importance":
            return self._validate_feature_importance(component, data, remaining_height_mm)

        return component

    def _validate_chart(
        self,
        component: Dict,
        data: Dict,
        remaining_height_mm: float,
    ) -> Dict:
        """Validate chart and apply fallback ladder if needed."""
        chart_data = data.get("data", {})
        labels = chart_data.get("labels", [])
        num_items = len(labels)

        # Check 1: Too many bars — downgrade to table
        if num_items > _MAX_CHART_BARS:
            headers = ["Item", "Value"]
            datasets = chart_data.get("datasets", [{}])
            values = datasets[0].get("data", []) if datasets else []
            rows = [
                [str(labels[i]), str(values[i]) if i < len(values) else "0"]
                for i in range(min(10, num_items))
            ]
            table = build_table(headers, rows)

            # Check 2: Even table overflows
            table_height = len(rows) * self.ROW_HEIGHT_MM + 10  # header + padding
            if remaining_height_mm - table_height < self.MIN_REMAINING_MM:
                return build_paragraph(
                    f"{num_items} items identified. "
                    f"Top item: {labels[0]} ({values[0] if values else 'N/A'})."
                )
            return table

        # Check 3: Chart fits but barely — it's fine, proceed
        if remaining_height_mm < self.CHART_HEIGHT_MM:
            # Page break would be needed — just return the component and let
            # the PDF renderer handle page breaks
            pass

        return component

    def _validate_feature_importance(
        self,
        component: Dict,
        data: Dict,
        remaining_height_mm: float,
    ) -> Dict:
        """Validate SHAP feature importance display."""
        features = data.get("features", [])
        estimated_height = len(features) * 12 + 30  # bar height + legend

        if estimated_height > remaining_height_mm:
            # Downgrade to table
            headers = ["Feature", "Importance", "SHAP Value"]
            rows = [
                [f.get("feature", ""), f"{f.get('importance', 0):.3f}", f"{f.get('shap_value', 0):.3f}"]
                for f in features[:8]
            ]
            return build_table(headers, rows)

        return component

    def validate_ast(self, ast: Dict) -> Dict:
        """
        Walk all components in an AST and validate each one.
        Returns corrected AST.
        """
        if not isinstance(ast, dict):
            return ast

        content = ast.get("content", [])
        if not content:
            return ast

        validated_content = []
        remaining = self.USABLE_HEIGHT_MM

        for node in content:
            if node.get("type") == "component":
                node = self.validate_component(node, remaining)
                remaining -= self.CHART_HEIGHT_MM  # Approximate
            elif node.get("type") == "table":
                rows = len(node.get("content", [])) - 1  # minus header
                remaining -= rows * self.ROW_HEIGHT_MM + 10
            elif node.get("type") in ("heading", "paragraph"):
                remaining -= 8

            if remaining < self.MIN_REMAINING_MM:
                remaining = self.USABLE_HEIGHT_MM  # New page

            validated_content.append(node)

        return {**ast, "content": validated_content}

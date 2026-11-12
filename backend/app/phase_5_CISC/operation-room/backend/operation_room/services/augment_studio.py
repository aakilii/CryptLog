"""
Augment Studio - Dynamic Chart Generator

Provides on-demand chart generation from investigation data.
Supports multiple chart types with configurable data bindings.

Features:
- Pie charts, bar charts, area charts, radar charts
- Auto-detection of best chart type for data
- Real-time preview with SSE streaming
- Export to canvas elements
"""

import logging
from typing import Dict, Any, List, Optional, Literal
from datetime import datetime
from dataclasses import dataclass, field
from enum import Enum
import json

logger = logging.getLogger(__name__)


class ChartType(str, Enum):
    """Supported chart types."""
    PIE = "pie"
    BAR = "bar"
    LINE = "line"
    AREA = "area"
    RADAR = "radar"
    SCATTER = "scatter"
    HEATMAP = "heatmap"
    TREEMAP = "treemap"
    SANKEY = "sankey"
    TIMELINE = "timeline"
    NETWORK = "network"


@dataclass
class ChartConfig:
    """Configuration for a chart."""
    chart_type: ChartType
    title: str
    data: Dict[str, Any]
    width: int = 720
    height: int = 350
    colors: List[str] = field(default_factory=lambda: [
        "#10b981", "#3b82f6", "#f59e0b", "#ef4444", "#8b5cf6",
        "#06b6d4", "#ec4899", "#84cc16", "#f97316", "#6366f1"
    ])
    options: Dict[str, Any] = field(default_factory=dict)


@dataclass 
class ChartOutput:
    """Output from chart generation."""
    chart_type: ChartType
    title: str
    config: Dict[str, Any]
    data: Dict[str, Any]
    canvas_element: Dict[str, Any]


class AugmentStudioChartGenerator:
    """
    Dynamic chart generator for investigation data.
    
    Usage:
        generator = AugmentStudioChartGenerator()
        
        # Generate pie chart from severity distribution
        chart = generator.generate_pie_chart(
            title="Finding Severity Distribution",
            data={"critical": 5, "high": 12, "medium": 28, "low": 45}
        )
        
        # Auto-detect best chart type
        chart = generator.auto_generate(
            title="Event Timeline",
            data=[{"timestamp": "...", "count": 10}, ...]
        )
    """
    
    def __init__(self):
        self.default_colors = [
            "#10b981", "#3b82f6", "#f59e0b", "#ef4444", "#8b5cf6",
            "#06b6d4", "#ec4899", "#84cc16", "#f97316", "#6366f1"
        ]
    
    def generate_pie_chart(
        self,
        title: str,
        data: Dict[str, int | float],
        colors: Optional[List[str]] = None,
    ) -> ChartOutput:
        """
        Generate a pie chart from label-value pairs.
        
        Args:
            title: Chart title
            data: Dictionary of {label: value}
            colors: Optional custom color palette
        """
        colors = colors or self.default_colors
        
        # Convert to chart.js format
        labels = list(data.keys())
        values = list(data.values())
        
        chart_data = {
            "labels": labels,
            "datasets": [{
                "data": values,
                "backgroundColor": colors[:len(labels)],
                "borderColor": ["#ffffff"] * len(labels),
                "borderWidth": 2,
            }]
        }
        
        config = {
            "type": "pie",
            "data": chart_data,
            "options": {
                "responsive": True,
                "plugins": {
                    "legend": {"position": "right"},
                    "title": {"display": True, "text": title},
                },
            },
        }
        
        canvas_element = {
            "type": "component",
            "data": {
                "type": "chart",
                "chartType": "pie",
                "module": "augment",
                "componentId": "PieChart",
                "title": title,
                "data": chart_data,
                "config": config,
            },
            "width": 400,
            "height": 350,
        }
        
        return ChartOutput(
            chart_type=ChartType.PIE,
            title=title,
            config=config,
            data=chart_data,
            canvas_element=canvas_element,
        )
    
    def generate_bar_chart(
        self,
        title: str,
        data: Dict[str, int | float] | List[Dict[str, Any]],
        x_label: str = "",
        y_label: str = "",
        horizontal: bool = False,
        colors: Optional[List[str]] = None,
    ) -> ChartOutput:
        """
        Generate a bar chart.
        
        Args:
            title: Chart title
            data: Dictionary of {label: value} or list of {label, value}
            x_label: X-axis label
            y_label: Y-axis label
            horizontal: Whether to render horizontally
            colors: Optional custom color palette
        """
        colors = colors or self.default_colors
        
        if isinstance(data, dict):
            labels = list(data.keys())
            values = list(data.values())
        else:
            labels = [d.get("label", d.get("name", "")) for d in data]
            values = [d.get("value", d.get("count", 0)) for d in data]
        
        chart_data = {
            "labels": labels,
            "datasets": [{
                "label": y_label or "Count",
                "data": values,
                "backgroundColor": colors[:len(labels)],
                "borderColor": [c.replace(")", ", 0.8)").replace("rgb", "rgba") for c in colors[:len(labels)]],
                "borderWidth": 1,
            }]
        }
        
        config = {
            "type": "bar",
            "data": chart_data,
            "options": {
                "indexAxis": "y" if horizontal else "x",
                "responsive": True,
                "plugins": {
                    "legend": {"display": False},
                    "title": {"display": True, "text": title},
                },
                "scales": {
                    "x": {"title": {"display": bool(x_label), "text": x_label}},
                    "y": {"title": {"display": bool(y_label), "text": y_label}},
                },
            },
        }
        
        canvas_element = {
            "type": "component",
            "data": {
                "type": "chart",
                "chartType": "bar",
                "module": "augment",
                "componentId": "BarChart",
                "title": title,
                "data": chart_data,
                "config": config,
            },
            "width": 720,
            "height": 350,
        }
        
        return ChartOutput(
            chart_type=ChartType.BAR,
            title=title,
            config=config,
            data=chart_data,
            canvas_element=canvas_element,
        )
    
    def generate_line_chart(
        self,
        title: str,
        data: List[Dict[str, Any]],
        x_key: str = "timestamp",
        y_key: str = "value",
        x_label: str = "Time",
        y_label: str = "Value",
        fill: bool = False,
    ) -> ChartOutput:
        """
        Generate a line chart from time-series data.
        
        Args:
            title: Chart title
            data: List of {x_key: ..., y_key: ...}
            x_key: Key for x-axis values
            y_key: Key for y-axis values
            x_label: X-axis label
            y_label: Y-axis label
            fill: Whether to fill area under line
        """
        labels = [d.get(x_key, "") for d in data]
        values = [d.get(y_key, 0) for d in data]
        
        chart_data = {
            "labels": labels,
            "datasets": [{
                "label": y_label,
                "data": values,
                "borderColor": self.default_colors[0],
                "backgroundColor": f"{self.default_colors[0]}33",
                "fill": fill,
                "tension": 0.3,
            }]
        }
        
        chart_type = ChartType.AREA if fill else ChartType.LINE
        
        config = {
            "type": "line",
            "data": chart_data,
            "options": {
                "responsive": True,
                "plugins": {
                    "legend": {"display": False},
                    "title": {"display": True, "text": title},
                },
                "scales": {
                    "x": {"title": {"display": True, "text": x_label}},
                    "y": {"title": {"display": True, "text": y_label}},
                },
            },
        }
        
        canvas_element = {
            "type": "component",
            "data": {
                "type": "chart",
                "chartType": "line" if not fill else "area",
                "module": "augment",
                "componentId": "LineChart",
                "title": title,
                "data": chart_data,
                "config": config,
            },
            "width": 720,
            "height": 300,
        }
        
        return ChartOutput(
            chart_type=chart_type,
            title=title,
            config=config,
            data=chart_data,
            canvas_element=canvas_element,
        )
    
    def generate_radar_chart(
        self,
        title: str,
        data: Dict[str, float],
        max_value: float = 1.0,
    ) -> ChartOutput:
        """
        Generate a radar/spider chart for multi-dimensional data.
        
        Args:
            title: Chart title
            data: Dictionary of {dimension: value}
            max_value: Maximum value for scaling
        """
        labels = list(data.keys())
        values = list(data.values())
        
        chart_data = {
            "labels": labels,
            "datasets": [{
                "label": title,
                "data": values,
                "backgroundColor": f"{self.default_colors[0]}40",
                "borderColor": self.default_colors[0],
                "pointBackgroundColor": self.default_colors[0],
                "pointBorderColor": "#fff",
                "pointHoverBackgroundColor": "#fff",
                "pointHoverBorderColor": self.default_colors[0],
            }]
        }
        
        config = {
            "type": "radar",
            "data": chart_data,
            "options": {
                "responsive": True,
                "plugins": {
                    "title": {"display": True, "text": title},
                },
                "scales": {
                    "r": {
                        "beginAtZero": True,
                        "max": max_value,
                    }
                },
            },
        }
        
        canvas_element = {
            "type": "component",
            "data": {
                "type": "chart",
                "chartType": "radar",
                "module": "augment",
                "componentId": "RadarChart",
                "title": title,
                "data": chart_data,
                "config": config,
            },
            "width": 400,
            "height": 400,
        }
        
        return ChartOutput(
            chart_type=ChartType.RADAR,
            title=title,
            config=config,
            data=chart_data,
            canvas_element=canvas_element,
        )
    
    def generate_confidence_radar(
        self,
        factors: Dict[str, float],
        overall: float,
    ) -> ChartOutput:
        """
        Generate a radar chart for 6-factor confidence breakdown.
        
        Args:
            factors: Dictionary of {factor_name: score (0-1)}
            overall: Overall confidence score
        """
        # Format factor names for display
        formatted_factors = {}
        for key, value in factors.items():
            display_name = key.replace("_", " ").title()
            formatted_factors[display_name] = value
        
        return self.generate_radar_chart(
            title=f"Confidence Breakdown (Overall: {overall:.0%})",
            data=formatted_factors,
            max_value=1.0,
        )
    
    def auto_generate(
        self,
        title: str,
        data: Any,
        hint: Optional[str] = None,
    ) -> ChartOutput:
        """
        Auto-detect the best chart type for the given data.
        
        Args:
            title: Chart title
            data: Data in any supported format
            hint: Optional hint for chart type
        """
        # If hint provided, use it
        if hint:
            hint_lower = hint.lower()
            if "pie" in hint_lower:
                if isinstance(data, dict):
                    return self.generate_pie_chart(title, data)
            elif "bar" in hint_lower:
                return self.generate_bar_chart(title, data)
            elif "line" in hint_lower or "time" in hint_lower:
                return self.generate_line_chart(title, data)
            elif "radar" in hint_lower or "confidence" in hint_lower:
                if isinstance(data, dict):
                    return self.generate_radar_chart(title, data)
        
        # Auto-detect based on data structure
        if isinstance(data, dict):
            # Check if it looks like confidence factors
            if all(isinstance(v, (int, float)) and 0 <= v <= 1 for v in data.values()):
                if len(data) <= 8:
                    return self.generate_radar_chart(title, data)
            
            # Check for categorical data (pie/bar)
            if all(isinstance(v, (int, float)) for v in data.values()):
                if len(data) <= 6:
                    return self.generate_pie_chart(title, data)
                else:
                    return self.generate_bar_chart(title, data)
        
        elif isinstance(data, list):
            # Check for time-series
            if len(data) > 0 and isinstance(data[0], dict):
                if "timestamp" in data[0] or "date" in data[0] or "time" in data[0]:
                    return self.generate_line_chart(title, data)
                elif "label" in data[0] or "name" in data[0]:
                    return self.generate_bar_chart(title, data)
        
        # Default to bar chart
        if isinstance(data, dict):
            return self.generate_bar_chart(title, data)
        
        raise ValueError(f"Cannot auto-detect chart type for data: {type(data)}")
    
    def from_tool_output(
        self,
        tool_id: str,
        tool_output: Dict[str, Any],
    ) -> List[ChartOutput]:
        """
        Generate charts from a Universal Tool output.
        
        Args:
            tool_id: Tool identifier (timeline, anomaly, etc.)
            tool_output: Tool execution output
        """
        charts = []
        
        if tool_id == "timeline":
            # Timeline stats chart
            if "severity_breakdown" in tool_output:
                charts.append(self.generate_pie_chart(
                    title="Event Severity Distribution",
                    data=tool_output["severity_breakdown"],
                ))
            
            # Activity over time
            if "activity_by_hour" in tool_output:
                charts.append(self.generate_line_chart(
                    title="Activity by Hour",
                    data=tool_output["activity_by_hour"],
                    x_key="hour",
                    y_key="count",
                    fill=True,
                ))
        
        elif tool_id == "anomaly":
            if "score_distribution" in tool_output:
                charts.append(self.generate_bar_chart(
                    title="Anomaly Score Distribution",
                    data=tool_output["score_distribution"],
                    horizontal=True,
                ))
        
        elif tool_id == "confidence":
            if "factors" in tool_output:
                charts.append(self.generate_confidence_radar(
                    factors=tool_output["factors"],
                    overall=tool_output.get("overall", 0.5),
                ))
        
        return charts


# Global instance
chart_generator = AugmentStudioChartGenerator()

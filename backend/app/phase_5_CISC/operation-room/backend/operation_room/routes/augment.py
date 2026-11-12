"""
Augment Studio API Routes

REST endpoints for dynamic chart generation.
"""

import logging
from typing import Optional, List, Dict, Any
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field

from operation_room.services.augment_studio import chart_generator, ChartType

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api/augment", tags=["Augment Studio"])


# ─── Request/Response Models ─────────────────────────────────────────────────

class PieChartRequest(BaseModel):
    """Request for pie chart generation."""
    title: str = Field(..., description="Chart title")
    data: Dict[str, float] = Field(..., description="Label-value pairs")
    colors: Optional[List[str]] = Field(default=None, description="Custom color palette")


class BarChartRequest(BaseModel):
    """Request for bar chart generation."""
    title: str = Field(..., description="Chart title")
    data: Dict[str, float] | List[Dict[str, Any]] = Field(..., description="Data to chart")
    x_label: str = Field(default="", description="X-axis label")
    y_label: str = Field(default="", description="Y-axis label")
    horizontal: bool = Field(default=False, description="Horizontal bars")
    colors: Optional[List[str]] = Field(default=None, description="Custom colors")


class LineChartRequest(BaseModel):
    """Request for line/area chart generation."""
    title: str = Field(..., description="Chart title")
    data: List[Dict[str, Any]] = Field(..., description="Time-series data")
    x_key: str = Field(default="timestamp", description="Key for x-axis")
    y_key: str = Field(default="value", description="Key for y-axis")
    x_label: str = Field(default="Time", description="X-axis label")
    y_label: str = Field(default="Value", description="Y-axis label")
    fill: bool = Field(default=False, description="Fill area under line")


class RadarChartRequest(BaseModel):
    """Request for radar chart generation."""
    title: str = Field(..., description="Chart title")
    data: Dict[str, float] = Field(..., description="Dimension-value pairs")
    max_value: float = Field(default=1.0, description="Maximum scale value")


class ConfidenceRadarRequest(BaseModel):
    """Request for confidence breakdown radar chart."""
    factors: Dict[str, float] = Field(..., description="6-factor scores")
    overall: float = Field(..., description="Overall confidence score")


class AutoChartRequest(BaseModel):
    """Request for auto-detected chart generation."""
    title: str = Field(..., description="Chart title")
    data: Any = Field(..., description="Data in any format")
    hint: Optional[str] = Field(default=None, description="Chart type hint")


class ChartResponse(BaseModel):
    """Response containing generated chart."""
    chart_type: str
    title: str
    config: Dict[str, Any]
    data: Dict[str, Any]
    canvas_element: Dict[str, Any]


class ToolChartsRequest(BaseModel):
    """Request to generate charts from tool output."""
    tool_id: str = Field(..., description="Tool identifier")
    tool_output: Dict[str, Any] = Field(..., description="Tool execution output")


# ─── API Routes ──────────────────────────────────────────────────────────────

@router.post("/pie", response_model=ChartResponse)
async def generate_pie_chart(request: PieChartRequest) -> ChartResponse:
    """Generate a pie chart from label-value data."""
    try:
        result = chart_generator.generate_pie_chart(
            title=request.title,
            data=request.data,
            colors=request.colors,
        )
        return ChartResponse(
            chart_type=result.chart_type.value,
            title=result.title,
            config=result.config,
            data=result.data,
            canvas_element=result.canvas_element,
        )
    except Exception as e:
        logger.error(f"Pie chart generation failed: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/bar", response_model=ChartResponse)
async def generate_bar_chart(request: BarChartRequest) -> ChartResponse:
    """Generate a bar chart."""
    try:
        result = chart_generator.generate_bar_chart(
            title=request.title,
            data=request.data,
            x_label=request.x_label,
            y_label=request.y_label,
            horizontal=request.horizontal,
            colors=request.colors,
        )
        return ChartResponse(
            chart_type=result.chart_type.value,
            title=result.title,
            config=result.config,
            data=result.data,
            canvas_element=result.canvas_element,
        )
    except Exception as e:
        logger.error(f"Bar chart generation failed: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/line", response_model=ChartResponse)
async def generate_line_chart(request: LineChartRequest) -> ChartResponse:
    """Generate a line/area chart from time-series data."""
    try:
        result = chart_generator.generate_line_chart(
            title=request.title,
            data=request.data,
            x_key=request.x_key,
            y_key=request.y_key,
            x_label=request.x_label,
            y_label=request.y_label,
            fill=request.fill,
        )
        return ChartResponse(
            chart_type=result.chart_type.value,
            title=result.title,
            config=result.config,
            data=result.data,
            canvas_element=result.canvas_element,
        )
    except Exception as e:
        logger.error(f"Line chart generation failed: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/radar", response_model=ChartResponse)
async def generate_radar_chart(request: RadarChartRequest) -> ChartResponse:
    """Generate a radar/spider chart."""
    try:
        result = chart_generator.generate_radar_chart(
            title=request.title,
            data=request.data,
            max_value=request.max_value,
        )
        return ChartResponse(
            chart_type=result.chart_type.value,
            title=result.title,
            config=result.config,
            data=result.data,
            canvas_element=result.canvas_element,
        )
    except Exception as e:
        logger.error(f"Radar chart generation failed: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/confidence", response_model=ChartResponse)
async def generate_confidence_radar(request: ConfidenceRadarRequest) -> ChartResponse:
    """Generate a confidence breakdown radar chart."""
    try:
        result = chart_generator.generate_confidence_radar(
            factors=request.factors,
            overall=request.overall,
        )
        return ChartResponse(
            chart_type=result.chart_type.value,
            title=result.title,
            config=result.config,
            data=result.data,
            canvas_element=result.canvas_element,
        )
    except Exception as e:
        logger.error(f"Confidence radar generation failed: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/auto", response_model=ChartResponse)
async def auto_generate_chart(request: AutoChartRequest) -> ChartResponse:
    """Auto-detect best chart type and generate."""
    try:
        result = chart_generator.auto_generate(
            title=request.title,
            data=request.data,
            hint=request.hint,
        )
        return ChartResponse(
            chart_type=result.chart_type.value,
            title=result.title,
            config=result.config,
            data=result.data,
            canvas_element=result.canvas_element,
        )
    except Exception as e:
        logger.error(f"Auto chart generation failed: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/from-tool", response_model=List[ChartResponse])
async def generate_from_tool_output(request: ToolChartsRequest) -> List[ChartResponse]:
    """Generate charts from a Universal Tool output."""
    try:
        results = chart_generator.from_tool_output(
            tool_id=request.tool_id,
            tool_output=request.tool_output,
        )
        return [
            ChartResponse(
                chart_type=r.chart_type.value,
                title=r.title,
                config=r.config,
                data=r.data,
                canvas_element=r.canvas_element,
            )
            for r in results
        ]
    except Exception as e:
        logger.error(f"Tool chart generation failed: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/types")
async def list_chart_types() -> Dict[str, List[str]]:
    """List available chart types."""
    return {
        "chart_types": [ct.value for ct in ChartType],
        "endpoints": [
            "/api/augment/pie",
            "/api/augment/bar",
            "/api/augment/line",
            "/api/augment/radar",
            "/api/augment/confidence",
            "/api/augment/auto",
            "/api/augment/from-tool",
        ],
    }

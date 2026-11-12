"""
Coordinate Mapper for ReportLab PDF Generation.

Converts canvas pixel coordinates (96 DPI) to PDF points (72 DPI).
Handles the Y-axis inversion (canvas: top-left origin, PDF: bottom-left origin).
"""

from typing import Tuple, NamedTuple
from dataclasses import dataclass


class PageSize(NamedTuple):
    """Page dimensions in points."""
    width: float
    height: float


# Standard page sizes in points (72 DPI)
PAGE_SIZES = {
    'A4': PageSize(595.28, 841.89),
    'LETTER': PageSize(612, 792),
    'LEGAL': PageSize(612, 1008),
    'A3': PageSize(841.89, 1190.55),
}

# Canvas dimensions at 96 DPI
CANVAS_SIZES = {
    'A4': (794, 1123),  # pixels
    'LETTER': (816, 1056),
    'LEGAL': (816, 1344),
    'A3': (1123, 1587),
}


@dataclass
class BoundingBox:
    """Bounding box in PDF coordinates (points)."""
    x: float
    y: float
    width: float
    height: float
    
    @property
    def x2(self) -> float:
        return self.x + self.width
    
    @property
    def y2(self) -> float:
        return self.y + self.height


class CoordinateMapper:
    """
    Maps canvas pixel coordinates to PDF points.
    
    Canvas coordinate system:
    - Origin: top-left corner
    - X increases rightward
    - Y increases downward
    - Units: pixels at 96 DPI
    
    PDF coordinate system:
    - Origin: bottom-left corner
    - X increases rightward
    - Y increases upward
    - Units: points (1 point = 1/72 inch)
    
    Conversion: 1 pixel at 96 DPI = 0.75 points (72/96)
    """
    
    CANVAS_DPI = 96
    PDF_DPI = 72
    SCALE_FACTOR = PDF_DPI / CANVAS_DPI  # 0.75
    
    def __init__(self, page_size: str = 'A4', margins: Tuple[float, float, float, float] = (20, 20, 20, 20)):
        """
        Initialize the coordinate mapper.
        
        Args:
            page_size: Page size name ('A4', 'LETTER', 'LEGAL', 'A3')
            margins: Page margins in points (top, right, bottom, left)
        """
        self.page_size_name = page_size
        self.pdf_page_size = PAGE_SIZES.get(page_size, PAGE_SIZES['A4'])
        self.canvas_page_size = CANVAS_SIZES.get(page_size, CANVAS_SIZES['A4'])
        
        self.margin_top, self.margin_right, self.margin_bottom, self.margin_left = margins
        
        # Usable area in points
        self.usable_width = self.pdf_page_size.width - self.margin_left - self.margin_right
        self.usable_height = self.pdf_page_size.height - self.margin_top - self.margin_bottom
    
    def px_to_pt(self, px: float) -> float:
        """Convert pixels to points."""
        return px * self.SCALE_FACTOR
    
    def pt_to_px(self, pt: float) -> float:
        """Convert points to pixels."""
        return pt / self.SCALE_FACTOR
    
    def canvas_to_pdf_position(self, canvas_x: float, canvas_y: float, element_height: float = 0) -> Tuple[float, float]:
        """
        Convert canvas position to PDF position.
        
        Args:
            canvas_x: X position in canvas pixels (from left)
            canvas_y: Y position in canvas pixels (from top)
            element_height: Height of the element in pixels (needed for Y inversion)
        
        Returns:
            (pdf_x, pdf_y) in points, where pdf_y is from bottom
        """
        # Convert to points
        pdf_x = self.px_to_pt(canvas_x) + self.margin_left
        
        # Invert Y axis: canvas Y=0 is top, PDF Y=0 is bottom
        # Element top in canvas → Element bottom in PDF needs adjustment
        canvas_y_bottom = canvas_y + element_height
        pdf_y_from_top = self.px_to_pt(canvas_y_bottom)
        pdf_y = self.pdf_page_size.height - pdf_y_from_top - self.margin_top
        
        return pdf_x, pdf_y
    
    def canvas_to_pdf_size(self, canvas_width: float, canvas_height: float) -> Tuple[float, float]:
        """
        Convert canvas dimensions to PDF dimensions.
        
        Args:
            canvas_width: Width in canvas pixels
            canvas_height: Height in canvas pixels
        
        Returns:
            (pdf_width, pdf_height) in points
        """
        return self.px_to_pt(canvas_width), self.px_to_pt(canvas_height)
    
    def canvas_element_to_pdf_bbox(
        self, 
        canvas_x: float, 
        canvas_y: float, 
        canvas_width: float, 
        canvas_height: float
    ) -> BoundingBox:
        """
        Convert a canvas element's bounds to a PDF bounding box.
        
        Args:
            canvas_x: Element X position in pixels
            canvas_y: Element Y position in pixels
            canvas_width: Element width in pixels
            canvas_height: Element height in pixels
        
        Returns:
            BoundingBox in PDF points
        """
        pdf_width, pdf_height = self.canvas_to_pdf_size(canvas_width, canvas_height)
        pdf_x, pdf_y = self.canvas_to_pdf_position(canvas_x, canvas_y, canvas_height)
        
        return BoundingBox(
            x=pdf_x,
            y=pdf_y,
            width=pdf_width,
            height=pdf_height
        )
    
    def get_page_content_area(self) -> BoundingBox:
        """Get the usable content area of the page."""
        return BoundingBox(
            x=self.margin_left,
            y=self.margin_bottom,
            width=self.usable_width,
            height=self.usable_height
        )
    
    def is_within_page(self, bbox: BoundingBox) -> bool:
        """Check if a bounding box fits within the page margins."""
        content_area = self.get_page_content_area()
        return (
            bbox.x >= content_area.x and
            bbox.y >= content_area.y and
            bbox.x2 <= content_area.x2 and
            bbox.y2 <= content_area.y2
        )
    
    def clamp_to_page(self, bbox: BoundingBox) -> BoundingBox:
        """Clamp a bounding box to fit within the page margins."""
        content_area = self.get_page_content_area()
        
        x = max(bbox.x, content_area.x)
        y = max(bbox.y, content_area.y)
        
        # Adjust width/height if needed
        max_width = content_area.x2 - x
        max_height = content_area.y2 - y
        
        return BoundingBox(
            x=x,
            y=y,
            width=min(bbox.width, max_width),
            height=min(bbox.height, max_height)
        )


# Convenience functions
def create_a4_mapper(margins_mm: Tuple[float, float, float, float] = (10, 10, 10, 10)) -> CoordinateMapper:
    """
    Create an A4 coordinate mapper with margins in millimeters.
    
    Default margins are minimal (10mm) because canvas elements already account
    for their positioning. Adding large margins would push content too far right.
    """
    # Convert mm to points: 1 mm = 2.83465 points
    MM_TO_PT = 2.83465
    margins_pt = tuple(m * MM_TO_PT for m in margins_mm)
    return CoordinateMapper('A4', margins_pt)


def create_letter_mapper(margins_inches: Tuple[float, float, float, float] = (1, 0.75, 1, 0.75)) -> CoordinateMapper:
    """Create a Letter coordinate mapper with margins in inches."""
    # Convert inches to points: 1 inch = 72 points
    margins_pt = tuple(m * 72 for m in margins_inches)
    return CoordinateMapper('LETTER', margins_pt)

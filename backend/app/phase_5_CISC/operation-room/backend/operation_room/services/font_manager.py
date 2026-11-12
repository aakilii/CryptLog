"""
Font Manager for ReportLab PDF Generation.

Handles font registration and provides consistent font access
across all PDF generation. Uses embedded fonts to ensure
identical rendering across all platforms.
"""

import os
from pathlib import Path
from typing import Dict, Optional, Tuple
from dataclasses import dataclass
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
from reportlab.lib.fonts import addMapping
import logging

logger = logging.getLogger(__name__)


@dataclass
class FontFamily:
    """A font family with its variants."""
    name: str
    regular: str
    bold: Optional[str] = None
    italic: Optional[str] = None
    bold_italic: Optional[str] = None


# Default fallback fonts (built into ReportLab)
BUILTIN_FONTS = {
    'Helvetica': FontFamily(
        name='Helvetica',
        regular='Helvetica',
        bold='Helvetica-Bold',
        italic='Helvetica-Oblique',
        bold_italic='Helvetica-BoldOblique'
    ),
    'Times': FontFamily(
        name='Times',
        regular='Times-Roman',
        bold='Times-Bold',
        italic='Times-Italic',
        bold_italic='Times-BoldItalic'
    ),
    'Courier': FontFamily(
        name='Courier',
        regular='Courier',
        bold='Courier-Bold',
        italic='Courier-Oblique',
        bold_italic='Courier-BoldOblique'
    ),
}

# Font weight/style to suffix mapping
FONT_VARIANTS = {
    ('normal', 'normal'): '',
    ('bold', 'normal'): '-Bold',
    ('normal', 'italic'): '-Italic',
    ('bold', 'italic'): '-BoldItalic',
}


class FontManager:
    """
    Manages font registration and access for ReportLab PDF generation.
    
    Supports:
    - Built-in ReportLab fonts (Helvetica, Times, Courier)
    - Custom TTF fonts (embedded in PDF for consistent rendering)
    - Font family mapping with variants (regular, bold, italic, bold-italic)
    """
    
    _instance = None
    _initialized = False
    
    def __new__(cls):
        """Singleton pattern - only one font manager needed."""
        if cls._instance is None:
            cls._instance = super().__new__(cls)
        return cls._instance
    
    def __init__(self):
        if FontManager._initialized:
            return
            
        self._registered_fonts: Dict[str, FontFamily] = {}
        self._font_paths: Dict[str, Path] = {}
        self._default_family = 'Helvetica'
        
        # Register built-in fonts
        for name, family in BUILTIN_FONTS.items():
            self._registered_fonts[name] = family
        
        FontManager._initialized = True
    
    def register_ttf_font(
        self, 
        family_name: str,
        regular_path: str,
        bold_path: Optional[str] = None,
        italic_path: Optional[str] = None,
        bold_italic_path: Optional[str] = None
    ) -> bool:
        """
        Register a TTF font family with ReportLab.
        
        Args:
            family_name: Name to use for this font family
            regular_path: Path to regular weight TTF file
            bold_path: Path to bold weight TTF file (optional)
            italic_path: Path to italic TTF file (optional)
            bold_italic_path: Path to bold italic TTF file (optional)
        
        Returns:
            True if registration successful
        """
        try:
            # Register regular font (required)
            regular_name = family_name
            pdfmetrics.registerFont(TTFont(regular_name, regular_path))
            self._font_paths[regular_name] = Path(regular_path)
            
            # Register bold if provided
            bold_name = f"{family_name}-Bold"
            if bold_path and os.path.exists(bold_path):
                pdfmetrics.registerFont(TTFont(bold_name, bold_path))
                self._font_paths[bold_name] = Path(bold_path)
            else:
                bold_name = regular_name  # Fallback to regular
            
            # Register italic if provided
            italic_name = f"{family_name}-Italic"
            if italic_path and os.path.exists(italic_path):
                pdfmetrics.registerFont(TTFont(italic_name, italic_path))
                self._font_paths[italic_name] = Path(italic_path)
            else:
                italic_name = regular_name  # Fallback to regular
            
            # Register bold italic if provided
            bold_italic_name = f"{family_name}-BoldItalic"
            if bold_italic_path and os.path.exists(bold_italic_path):
                pdfmetrics.registerFont(TTFont(bold_italic_name, bold_italic_path))
                self._font_paths[bold_italic_name] = Path(bold_italic_path)
            else:
                bold_italic_name = bold_name  # Fallback to bold
            
            # Register font family mapping
            addMapping(family_name, 0, 0, regular_name)      # normal, normal
            addMapping(family_name, 1, 0, bold_name)         # bold, normal
            addMapping(family_name, 0, 1, italic_name)       # normal, italic
            addMapping(family_name, 1, 1, bold_italic_name)  # bold, italic
            
            # Store family info
            self._registered_fonts[family_name] = FontFamily(
                name=family_name,
                regular=regular_name,
                bold=bold_name,
                italic=italic_name,
                bold_italic=bold_italic_name
            )
            
            logger.info(f"Registered font family: {family_name}")
            return True
            
        except Exception as e:
            logger.error(f"Failed to register font {family_name}: {e}")
            return False
    
    def register_fonts_from_directory(self, fonts_dir: str, family_name: str) -> bool:
        """
        Register fonts from a directory using naming convention.
        
        Expects files named:
        - {family_name}-Regular.ttf
        - {family_name}-Bold.ttf
        - {family_name}-Italic.ttf
        - {family_name}-BoldItalic.ttf
        
        Args:
            fonts_dir: Directory containing font files
            family_name: Font family name (e.g., 'Inter', 'Roboto')
        
        Returns:
            True if at least regular font was registered
        """
        fonts_path = Path(fonts_dir)
        
        regular = fonts_path / f"{family_name}-Regular.ttf"
        if not regular.exists():
            # Try without -Regular suffix
            regular = fonts_path / f"{family_name}.ttf"
        
        if not regular.exists():
            logger.error(f"Regular font not found: {regular}")
            return False
        
        bold = fonts_path / f"{family_name}-Bold.ttf"
        italic = fonts_path / f"{family_name}-Italic.ttf"
        bold_italic = fonts_path / f"{family_name}-BoldItalic.ttf"
        
        return self.register_ttf_font(
            family_name=family_name,
            regular_path=str(regular),
            bold_path=str(bold) if bold.exists() else None,
            italic_path=str(italic) if italic.exists() else None,
            bold_italic_path=str(bold_italic) if bold_italic.exists() else None
        )
    
    def get_font_name(
        self, 
        family: Optional[str] = None, 
        weight: str = 'normal', 
        style: str = 'normal'
    ) -> str:
        """
        Get the ReportLab font name for a family/weight/style combination.
        
        Args:
            family: Font family name (defaults to default family)
            weight: 'normal' or 'bold'
            style: 'normal' or 'italic'
        
        Returns:
            ReportLab font name string
        """
        family = family or self._default_family
        font_family = self._registered_fonts.get(family)
        
        if not font_family:
            logger.warning(f"Font family '{family}' not found, using {self._default_family}")
            font_family = self._registered_fonts[self._default_family]
        
        if weight == 'bold' and style == 'italic':
            return font_family.bold_italic or font_family.bold or font_family.regular
        elif weight == 'bold':
            return font_family.bold or font_family.regular
        elif style == 'italic':
            return font_family.italic or font_family.regular
        else:
            return font_family.regular
    
    def set_default_family(self, family: str) -> None:
        """Set the default font family."""
        if family in self._registered_fonts:
            self._default_family = family
        else:
            logger.warning(f"Font family '{family}' not registered, keeping {self._default_family}")
    
    def get_registered_families(self) -> list:
        """Get list of all registered font family names."""
        return list(self._registered_fonts.keys())
    
    def is_registered(self, family: str) -> bool:
        """Check if a font family is registered."""
        return family in self._registered_fonts


# Font style definitions for common use cases
class FontStyles:
    """Predefined font styles for common text types."""
    
    # Headings
    H1 = {'fontName': 'Helvetica-Bold', 'fontSize': 24, 'leading': 28}
    H2 = {'fontName': 'Helvetica-Bold', 'fontSize': 18, 'leading': 22}
    H3 = {'fontName': 'Helvetica-Bold', 'fontSize': 14, 'leading': 18}
    H4 = {'fontName': 'Helvetica-Bold', 'fontSize': 12, 'leading': 16}
    
    # Body text
    BODY = {'fontName': 'Helvetica', 'fontSize': 10, 'leading': 14}
    BODY_SMALL = {'fontName': 'Helvetica', 'fontSize': 9, 'leading': 12}
    BODY_LARGE = {'fontName': 'Helvetica', 'fontSize': 11, 'leading': 15}
    
    # Special text
    CAPTION = {'fontName': 'Helvetica', 'fontSize': 8, 'leading': 10}
    LABEL = {'fontName': 'Helvetica-Bold', 'fontSize': 9, 'leading': 11}
    CODE = {'fontName': 'Courier', 'fontSize': 9, 'leading': 11}
    
    # Metrics/values
    METRIC_VALUE = {'fontName': 'Helvetica-Bold', 'fontSize': 28, 'leading': 32}
    METRIC_LABEL = {'fontName': 'Helvetica', 'fontSize': 10, 'leading': 12}
    
    @classmethod
    def get_style(cls, style_name: str) -> dict:
        """Get a style dict by name."""
        return getattr(cls, style_name.upper(), cls.BODY)
    
    @classmethod
    def with_font_family(cls, style: dict, family: str) -> dict:
        """
        Create a new style dict with a different font family.
        Preserves weight (bold) from original font name.
        """
        font_manager = FontManager()
        original_font = style.get('fontName', 'Helvetica')
        
        # Determine weight from original font name
        weight = 'bold' if 'Bold' in original_font else 'normal'
        style_type = 'italic' if 'Italic' in original_font or 'Oblique' in original_font else 'normal'
        
        new_font = font_manager.get_font_name(family, weight, style_type)
        
        return {**style, 'fontName': new_font}


# NFLIP brand colors for text
class NFLIPColors:
    """NFLIP brand colors for PDF text and elements."""
    
    PRIMARY = '#2563eb'      # Blue
    SECONDARY = '#7c3aed'    # Purple
    SUCCESS = '#10b981'      # Green
    WARNING = '#f59e0b'      # Amber
    DANGER = '#ef4444'       # Red
    INFO = '#06b6d4'         # Cyan
    
    TEXT_PRIMARY = '#1e293b'   # Slate 800
    TEXT_SECONDARY = '#64748b' # Slate 500
    TEXT_MUTED = '#94a3b8'     # Slate 400
    
    BORDER = '#e2e8f0'         # Slate 200
    BACKGROUND = '#f8fafc'     # Slate 50
    
    # Severity colors
    SEVERITY_CRITICAL = '#dc2626'
    SEVERITY_HIGH = '#ef4444'
    SEVERITY_MEDIUM = '#f59e0b'
    SEVERITY_LOW = '#10b981'
    SEVERITY_INFO = '#6b7280'
    
    @classmethod
    def hex_to_rgb(cls, hex_color: str) -> Tuple[float, float, float]:
        """Convert hex color to RGB tuple (0-1 range for ReportLab)."""
        hex_color = hex_color.lstrip('#')
        r = int(hex_color[0:2], 16) / 255
        g = int(hex_color[2:4], 16) / 255
        b = int(hex_color[4:6], 16) / 255
        return (r, g, b)
    
    @classmethod
    def get_severity_color(cls, severity: str) -> str:
        """Get color for a severity level."""
        severity_map = {
            'CRITICAL': cls.SEVERITY_CRITICAL,
            'HIGH': cls.SEVERITY_HIGH,
            'MEDIUM': cls.SEVERITY_MEDIUM,
            'LOW': cls.SEVERITY_LOW,
            'INFO': cls.SEVERITY_INFO,
        }
        return severity_map.get(severity.upper(), cls.SEVERITY_INFO)


def initialize_fonts(fonts_dir: Optional[str] = None) -> FontManager:
    """
    Initialize fonts for PDF generation.
    
    Args:
        fonts_dir: Optional directory containing custom fonts
    
    Returns:
        Configured FontManager instance
    """
    font_manager = FontManager()
    
    if fonts_dir and os.path.isdir(fonts_dir):
        # Try to register common font families
        for family in ['Inter', 'Roboto', 'OpenSans', 'Lato']:
            font_manager.register_fonts_from_directory(fonts_dir, family)
    
    return font_manager

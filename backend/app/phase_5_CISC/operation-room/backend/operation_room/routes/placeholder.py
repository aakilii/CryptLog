from fastapi import APIRouter
from fastapi.responses import Response

router = APIRouter(prefix="/api/placeholder", tags=["UI"])

@router.get("/{name:path}")
def generate_placeholder(name: str):
    """
    Generate an SVG placeholder image for missing UI assets.
    """
    # Remove extension if any
    base_name = name.split(".")[0]
    
    # Try to make it a bit varied based on length
    hues = [210, 220, 230, 240, 260, 270, 280, 290]
    hue = hues[len(base_name) % len(hues)]
    
    svg = f"""<svg width="400" height="250" xmlns="http://www.w3.org/2000/svg">
  <defs>
    <linearGradient id="grad" x1="0%" y1="0%" x2="100%" y2="100%">
      <stop offset="0%" style="stop-color:hsl({hue}, 60%, 85%);stop-opacity:1" />
      <stop offset="100%" style="stop-color:hsl({(hue+30)%360}, 60%, 90%);stop-opacity:1" />
    </linearGradient>
  </defs>
  <rect width="100%" height="100%" fill="url(#grad)"/>
  <rect width="90%" height="80%" x="5%" y="10%" rx="8" fill="white" opacity="0.6"/>
  <g fill="hsl({hue}, 40%, 40%)" font-family="-apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, Helvetica, Arial, sans-serif" text-anchor="middle">
    <!-- Icon representation -->
    <path d="M160 85 h80 v10 h-80 z M160 105 h80 v10 h-80 z M160 125 h60 v10 h-60 z" />
    <circle cx="200" cy="110" r="40" fill="none" stroke="hsl({hue}, 40%, 50%)" stroke-width="4" opacity="0.4"/>
    <text x="50%" y="190" font-size="16" font-weight="bold" letter-spacing="0.5">{base_name.replace('-', ' ').title()}</text>
  </g>
</svg>"""
    return Response(content=svg, media_type="image/svg+xml")

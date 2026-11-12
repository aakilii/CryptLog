from __future__ import annotations

from operation_room.services.template_library import list_templates


TEMPLATES = {template["id"]: template for template in list_templates()}

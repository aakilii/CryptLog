from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


@dataclass(frozen=True)
class TemplateChoice:
    id: str
    name: str
    image: str | None = None


@dataclass(frozen=True)
class TemplateZone:
    zone_id: str
    zone_type: str
    x: float
    y: float
    width: float
    height: float
    data_binding: str | None = None
    fallback_text: str | None = None


@dataclass(frozen=True)
class ReportTemplate:
    template_id: str
    name: str
    description: str
    category: str
    thumbnail: str
    color: str
    covers: list[TemplateChoice] = field(default_factory=list)
    fonts: list[TemplateChoice] = field(default_factory=list)
    graphs: list[TemplateChoice] = field(default_factory=list)
    tables: list[TemplateChoice] = field(default_factory=list)
    zones: list[TemplateZone] = field(default_factory=list)
    required_modules: list[str] = field(default_factory=list)
    schema_version: str = "v1"

    def to_api_dict(self) -> dict[str, Any]:
        return {
            "id": self.template_id,
            "name": self.name,
            "description": self.description,
            "category": self.category,
            "thumbnail": self.thumbnail,
            "color": self.color,
            "covers": [choice.__dict__ for choice in self.covers],
            "fonts": [choice.__dict__ for choice in self.fonts],
            "graphs": [choice.__dict__ for choice in self.graphs],
            "tables": [choice.__dict__ for choice in self.tables],
            "zones": [zone.__dict__ for zone in self.zones],
            "required_modules": self.required_modules,
            "schema_version": self.schema_version,
        }

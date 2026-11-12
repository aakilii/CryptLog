from __future__ import annotations

from operation_room.services.template_schema import ReportTemplate, TemplateChoice, TemplateZone


_DEFAULT_FONTS = [
    TemplateChoice(id="times", name="Times New Roman"),
    TemplateChoice(id="georgia", name="Georgia"),
    TemplateChoice(id="helvetica", name="Helvetica"),
]

_DEFAULT_GRAPHS = [
    TemplateChoice(id="classic", name="Classic Graphs"),
    TemplateChoice(id="modern", name="Modern Graphs"),
    TemplateChoice(id="minimal", name="Minimal Graphs"),
]

_DEFAULT_TABLES = [
    TemplateChoice(id="clean", name="Clean Table"),
    TemplateChoice(id="grid", name="Grid Table"),
    TemplateChoice(id="dark", name="Dark Header Table"),
]


def _covers(template_id: str) -> list[TemplateChoice]:
    return [
        TemplateChoice(id="cover_1", name="Cover 1", image=f"/templates/{template_id}/cover_1.png"),
        TemplateChoice(id="cover_2", name="Cover 2", image=f"/templates/{template_id}/cover_2.png"),
        TemplateChoice(id="cover_3", name="Cover 3", image=f"/templates/{template_id}/cover_3.png"),
    ]


BUILT_IN_TEMPLATES: dict[str, ReportTemplate] = {
    "executive-summary": ReportTemplate(
        template_id="executive-summary",
        name="Executive Summary",
        description="Leadership-ready summary with key signals, impact, and recommendations.",
        category="ir",
        thumbnail="/templates/executive-summary/thumb.png",
        color="#0f766e",
        covers=_covers("executive-summary"),
        fonts=_DEFAULT_FONTS,
        graphs=_DEFAULT_GRAPHS,
        tables=_DEFAULT_TABLES,
        required_modules=["timeline", "anomaly", "network", "depth"],
        zones=[
            TemplateZone("header", "header", 0.04, 0.04, 0.92, 0.12, "case.title"),
            TemplateZone("metrics", "metric-row", 0.04, 0.18, 0.92, 0.12, "summary.key_metrics"),
            TemplateZone("timeline", "chart", 0.04, 0.32, 0.92, 0.24, "timeline.activity"),
            TemplateZone("findings", "section", 0.04, 0.58, 0.92, 0.30, "findings.critical"),
        ],
    ),
    "forensic-technical": ReportTemplate(
        template_id="forensic-technical",
        name="Forensic Technical Report",
        description="Deep technical narrative for investigators and DFIR teams.",
        category="malware",
        thumbnail="/templates/forensic-technical/thumb.png",
        color="#1d4ed8",
        covers=_covers("forensic-technical"),
        fonts=_DEFAULT_FONTS,
        graphs=_DEFAULT_GRAPHS,
        tables=_DEFAULT_TABLES,
        required_modules=["timeline", "anomaly", "correlation", "network", "depth", "crud"],
        zones=[
            TemplateZone("header", "header", 0.04, 0.04, 0.92, 0.10, "case.title"),
            TemplateZone("methodology", "section", 0.04, 0.16, 0.92, 0.12, "methodology"),
            TemplateZone("anomaly-scatter", "chart", 0.04, 0.30, 0.44, 0.24, "anomalies.scatter"),
            TemplateZone("timeline-area", "chart", 0.52, 0.30, 0.44, 0.24, "timeline.area"),
            TemplateZone("correlation", "chart", 0.04, 0.56, 0.44, 0.24, "correlation.graph"),
            TemplateZone("network", "table", 0.52, 0.56, 0.44, 0.24, "network.flows"),
        ],
    ),
    "incident-response": ReportTemplate(
        template_id="incident-response",
        name="Incident Response Playbook",
        description="Action-oriented incident report with timeline, ownership, and response status.",
        category="network",
        thumbnail="/templates/incident-response/thumb.png",
        color="#b45309",
        covers=_covers("incident-response"),
        fonts=_DEFAULT_FONTS,
        graphs=_DEFAULT_GRAPHS,
        tables=_DEFAULT_TABLES,
        required_modules=["timeline", "network", "depth"],
        zones=[
            TemplateZone("header", "header", 0.04, 0.04, 0.92, 0.10, "case.title"),
            TemplateZone("impact", "section", 0.04, 0.16, 0.92, 0.14, "impact.summary"),
            TemplateZone("timeline", "chart", 0.04, 0.32, 0.92, 0.24, "timeline.activity"),
            TemplateZone("actions", "table", 0.04, 0.58, 0.92, 0.28, "response.actions"),
        ],
    ),
    "compliance-audit": ReportTemplate(
        template_id="compliance-audit",
        name="Compliance & Audit Pack",
        description="Evidence-heavy format for compliance and legal stakeholders.",
        category="insider",
        thumbnail="/templates/compliance-audit/thumb.png",
        color="#7c3aed",
        covers=_covers("compliance-audit"),
        fonts=_DEFAULT_FONTS,
        graphs=_DEFAULT_GRAPHS,
        tables=_DEFAULT_TABLES,
        required_modules=["timeline", "crud", "depth", "evidence"],
        zones=[
            TemplateZone("header", "header", 0.04, 0.04, 0.92, 0.10, "case.title"),
            TemplateZone("scope", "section", 0.04, 0.16, 0.92, 0.12, "audit.scope"),
            TemplateZone("violations", "table", 0.04, 0.30, 0.92, 0.20, "audit.violations"),
            TemplateZone("timeline", "chart", 0.04, 0.52, 0.92, 0.20, "timeline.regulatory"),
            TemplateZone("evidence", "section", 0.04, 0.74, 0.92, 0.16, "evidence.registry"),
        ],
    ),
}


def list_templates() -> list[dict]:
    return [template.to_api_dict() for template in BUILT_IN_TEMPLATES.values()]

"""
Key Placeholder Service

Handles key↔value replacements for LLM prompts and reports.

Architecture:
1. When generating summaries, LLM receives KEYS (not raw values)
2. LLM returns responses with KEY placeholders
3. System replaces keys with actual values before display
4. In report UI: values visible, hovering shows the key

This ensures:
- Sensitive data is not exposed to LLM
- Values can be updated and reports auto-refresh
- Full traceability via keys
- Consistent referencing across the system
"""

import re
import json
import logging
from typing import Dict, Any, List, Optional, Tuple
from dataclasses import dataclass, field
from datetime import datetime

from operation_room.services.findings_vault import FindingsVault

logger = logging.getLogger(__name__)


@dataclass
class KeyReference:
    """Represents a key reference in text."""
    key: str
    value: Any
    start_pos: int
    end_pos: int
    formatted_value: str = ""


@dataclass
class PlaceholderResult:
    """Result of placeholder operations."""
    original_text: str
    processed_text: str
    keys_found: List[str] = field(default_factory=list)
    keys_replaced: List[str] = field(default_factory=list)
    keys_not_found: List[str] = field(default_factory=list)
    reference_map: Dict[str, Any] = field(default_factory=dict)


class KeyPlaceholderService:
    """
    Service for key↔value placeholder operations.
    
    Supports two modes:
    1. Prompt Mode: Replace values with keys for LLM prompts
    2. Display Mode: Replace keys with values for display
    """
    
    # Pattern to match keys in text: {{KEY_NAME}}, {{key:KEY_NAME}}, [[KEY_NAME]], @KEY(KEY_NAME)
    KEY_PATTERNS = [
        r'\{\{key:([A-Z][A-Z0-9_]+)\}\}',  # {{key:KEY_NAME}}
        r'\{\{([A-Z][A-Z0-9_]+)\}\}',  # {{KEY_NAME}}
        r'\[\[([A-Z][A-Z0-9_]+)\]\]',  # [[KEY_NAME]]
        r'@KEY\(([A-Z][A-Z0-9_]+)\)',  # @KEY(KEY_NAME)
    ]
    
    # Known key prefixes for pattern matching
    KEY_PREFIXES = [
        'ANOM', 'NET', 'EXFIL', 'ACT', 'ENT', 'EVD', 'HYP',
        'MET', 'TML', 'COR', 'CON', 'CRUD', 'DEP', 'SYS', 'FILE', 'TEST'
    ]
    
    def __init__(self, case_id: str):
        self.case_id = case_id
        self.vault = FindingsVault(case_id)
        self._key_cache: Dict[str, Any] = {}
        self._cache_timestamp: Optional[datetime] = None
    
    def _refresh_cache(self, investigation_id: Optional[str] = None, force: bool = False):
        """Refresh the key-value cache from vault."""
        now = datetime.utcnow()
        if not force and self._cache_timestamp:
            # Cache valid for 60 seconds
            if (now - self._cache_timestamp).seconds < 60:
                return
        
        self._key_cache = self.vault.get_key_value_map(investigation_id=investigation_id)
        self._cache_timestamp = now
        logger.debug(f"Refreshed key cache with {len(self._key_cache)} entries")
    
    def _format_value_for_display(self, value: Any, max_length: int = 200) -> str:
        """Format a value for display in text."""
        if value is None:
            return "[No Value]"
        
        if isinstance(value, dict):
            # Format dict nicely
            if 'name' in value:
                return str(value['name'])
            if 'value' in value:
                return str(value['value'])
            if 'summary' in value:
                return str(value['summary'])[:max_length]
            # Generic dict
            formatted = json.dumps(value, indent=2)
            if len(formatted) > max_length:
                formatted = formatted[:max_length] + "..."
            return formatted
        
        if isinstance(value, list):
            if len(value) == 0:
                return "[Empty List]"
            # Join first few items
            items = [str(v) for v in value[:5]]
            result = ", ".join(items)
            if len(value) > 5:
                result += f" (+{len(value)-5} more)"
            return result
        
        # Simple value
        result = str(value)
        if len(result) > max_length:
            result = result[:max_length] + "..."
        return result
    
    def _format_value_for_prompt(self, key: str, value: Any) -> str:
        """Format a key-value pair for LLM prompt."""
        # Return the key with brackets for clear identification
        return f"{{{{key:{key}}}}}"
    
    # =========================================================================
    # PROMPT MODE: Replace values with keys for LLM
    # =========================================================================
    
    def prepare_prompt_with_keys(
        self,
        findings_data: Dict[str, Any],
        investigation_id: Optional[str] = None
    ) -> Tuple[str, Dict[str, str]]:
        """
        Prepare data for LLM prompt by storing values and returning keys.
        
        Args:
            findings_data: Dictionary of findings to prepare
            investigation_id: Optional investigation ID
        
        Returns:
            Tuple of (prompt_text, key_map)
            - prompt_text: Text with values replaced by keys
            - key_map: Map of keys to original values for replacement
        """
        self._refresh_cache(investigation_id)
        
        key_map = {}
        prompt_lines = []
        
        for category, items in findings_data.items():
            prompt_lines.append(f"\n## {category}")
            
            if isinstance(items, dict):
                for key, value in items.items():
                    # Check if this is already a vault key
                    if key.upper() in self._key_cache:
                        key_map[key.upper()] = self._key_cache[key.upper()]
                        prompt_lines.append(f"- {key}: {{{{key:{key.upper()}}}}}")
                    else:
                        # Store in cache for reference
                        key_map[key] = value
                        prompt_lines.append(f"- {key}: {{{{key:{key}}}}}")
            
            elif isinstance(items, list):
                for i, item in enumerate(items):
                    if isinstance(item, dict):
                        item_key = item.get('key', f"{category}_{i}")
                        if item_key in self._key_cache:
                            key_map[item_key] = self._key_cache[item_key]
                        else:
                            key_map[item_key] = item
                        prompt_lines.append(f"- Item {i}: {{{{key:{item_key}}}}}")
                    else:
                        prompt_lines.append(f"- {item}")
        
        return "\n".join(prompt_lines), key_map
    
    def create_summary_prompt(
        self,
        context: str,
        investigation_id: Optional[str] = None
    ) -> Tuple[str, Dict[str, Any]]:
        """
        Create a prompt for summary generation with key references.
        
        Args:
            context: The context/instructions for summary
            investigation_id: Investigation ID to load keys from
        
        Returns:
            Tuple of (prompt, key_map)
        """
        self._refresh_cache(investigation_id, force=True)
        
        # Build the key reference section
        key_refs = []
        for key, value in self._key_cache.items():
            # Create concise description
            if isinstance(value, dict):
                desc = value.get('summary', value.get('description', str(value)[:100]))
            elif isinstance(value, list):
                desc = f"List with {len(value)} items"
            else:
                desc = str(value)[:100]
            
            key_refs.append(f"- {{{{key:{key}}}}} = {desc}")
        
        prompt = f"""
{context}

## Available Data Keys
The following keys reference data from the investigation. Use these keys in your response
and they will be replaced with actual values in the final output.

{chr(10).join(key_refs[:50])}  # Limit to 50 keys in prompt

## Instructions
- Reference data using {{{{key:KEY_NAME}}}} format
- Be specific about which findings support your conclusions
- The keys will be replaced with actual values in the final report
"""
        
        return prompt, dict(self._key_cache)
    
    # =========================================================================
    # DISPLAY MODE: Replace keys with values
    # =========================================================================
    
    def replace_keys_with_values(
        self,
        text: str,
        investigation_id: Optional[str] = None,
        key_map: Optional[Dict[str, Any]] = None
    ) -> PlaceholderResult:
        """
        Replace key placeholders in text with actual values.
        
        Args:
            text: Text containing key placeholders
            investigation_id: Investigation ID to load keys from
            key_map: Optional pre-loaded key map
        
        Returns:
            PlaceholderResult with processed text and metadata
        """
        if key_map is None:
            self._refresh_cache(investigation_id, force=True)
            key_map = self._key_cache
        
        result = PlaceholderResult(
            original_text=text,
            processed_text=text,
            reference_map={}
        )
        
        # Find and replace all key patterns
        for pattern in self.KEY_PATTERNS:
            matches = list(re.finditer(pattern, result.processed_text))
            
            # Replace from end to preserve positions
            for match in reversed(matches):
                key = match.group(1)
                result.keys_found.append(key)
                
                if key in key_map:
                    value = key_map[key]
                    formatted = self._format_value_for_display(value)
                    result.keys_replaced.append(key)
                    result.reference_map[key] = value
                    
                    # Replace the match
                    start, end = match.span()
                    result.processed_text = (
                        result.processed_text[:start] +
                        formatted +
                        result.processed_text[end:]
                    )
                else:
                    result.keys_not_found.append(key)
                    logger.warning(f"Key not found in vault: {key}")
        
        return result
    
    def replace_values_with_keys(
        self,
        text: str,
        investigation_id: Optional[str] = None
    ) -> PlaceholderResult:
        """
        Replace known values in text with their keys (for prompt preparation).
        
        Args:
            text: Text potentially containing raw values
            investigation_id: Investigation ID
        
        Returns:
            PlaceholderResult with values replaced by keys
        """
        self._refresh_cache(investigation_id, force=True)
        
        result = PlaceholderResult(
            original_text=text,
            processed_text=text,
            reference_map={}
        )
        
        # Sort keys by value length (longest first) to avoid partial replacements
        sorted_items = sorted(
            self._key_cache.items(),
            key=lambda x: len(str(x[1])) if isinstance(x[1], str) else 0,
            reverse=True
        )
        
        for key, value in sorted_items:
            if isinstance(value, str) and len(value) > 5:
                # Check if value exists in text
                if value in result.processed_text:
                    result.processed_text = result.processed_text.replace(
                        value,
                        f"{{{{key:{key}}}}}"
                    )
                    result.keys_replaced.append(key)
                    result.reference_map[key] = value
        
        return result
    
    # =========================================================================
    # HTML OUTPUT: Values with key hover
    # =========================================================================
    
    def generate_html_with_hover_keys(
        self,
        text: str,
        investigation_id: Optional[str] = None,
        key_map: Optional[Dict[str, Any]] = None
    ) -> str:
        """
        Generate HTML where values are visible but keys appear on hover.
        
        Args:
            text: Text with key placeholders
            investigation_id: Investigation ID
            key_map: Optional pre-loaded key map
        
        Returns:
            HTML string with hover tooltips
        """
        if key_map is None:
            self._refresh_cache(investigation_id, force=True)
            key_map = self._key_cache
        
        html_output = text
        
        for pattern in self.KEY_PATTERNS:
            def replace_with_hover(match):
                key = match.group(1)
                if key in key_map:
                    value = key_map[key]
                    formatted = self._format_value_for_display(value)
                    # Escape HTML in value
                    formatted_html = self._escape_html(formatted)
                    return f'<span class="key-reference" data-key="{key}" title="Key: {key}">{formatted_html}</span>'
                return match.group(0)  # Keep original if not found
            
            html_output = re.sub(pattern, replace_with_hover, html_output)
        
        return html_output
    
    def _escape_html(self, text: str) -> str:
        """Escape HTML special characters."""
        return (text
            .replace("&", "&amp;")
            .replace("<", "&lt;")
            .replace(">", "&gt;")
            .replace('"', "&quot;")
            .replace("'", "&#39;"))
    
    # =========================================================================
    # REPORT EXPORT: Footnotes and references
    # =========================================================================
    
    def generate_report_with_footnotes(
        self,
        text: str,
        investigation_id: Optional[str] = None,
        key_map: Optional[Dict[str, Any]] = None
    ) -> Tuple[str, List[Dict[str, Any]]]:
        """
        Generate report text with footnotes for key references.
        
        Args:
            text: Text with key placeholders
            investigation_id: Investigation ID
            key_map: Optional pre-loaded key map
        
        Returns:
            Tuple of (report_text, footnotes)
            - report_text: Text with footnote markers
            - footnotes: List of footnote data
        """
        if key_map is None:
            self._refresh_cache(investigation_id, force=True)
            key_map = self._key_cache
        
        report_text = text
        footnotes = []
        footnote_number = 1
        
        for pattern in self.KEY_PATTERNS:
            def replace_with_footnote(match):
                nonlocal footnote_number
                key = match.group(1)
                
                if key in key_map:
                    value = key_map[key]
                    formatted = self._format_value_for_display(value)
                    
                    footnotes.append({
                        "number": footnote_number,
                        "key": key,
                        "value": value,
                        "formatted_value": formatted
                    })
                    
                    result = f"{formatted}[^{footnote_number}]"
                    footnote_number += 1
                    return result
                
                return match.group(0)
            
            report_text = re.sub(pattern, replace_with_footnote, report_text)
        
        return report_text, footnotes
    
    def format_footnotes_section(self, footnotes: List[Dict[str, Any]]) -> str:
        """Format footnotes for report appendix."""
        if not footnotes:
            return ""
        
        lines = ["\n---\n## Data References\n"]
        
        for fn in footnotes:
            lines.append(f"[^{fn['number']}]: **{fn['key']}** - {fn['formatted_value'][:100]}")
        
        return "\n".join(lines)
    
    # =========================================================================
    # VALIDATION
    # =========================================================================
    
    def validate_keys_in_text(
        self,
        text: str,
        investigation_id: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Validate all keys referenced in text exist in vault.
        
        Args:
            text: Text to validate
            investigation_id: Investigation ID
        
        Returns:
            Validation result with found/missing keys
        """
        self._refresh_cache(investigation_id, force=True)
        
        all_keys = set()
        for pattern in self.KEY_PATTERNS:
            matches = re.findall(pattern, text)
            all_keys.update(matches)
        
        found_keys = [k for k in all_keys if k in self._key_cache]
        missing_keys = [k for k in all_keys if k not in self._key_cache]
        
        return {
            "valid": len(missing_keys) == 0,
            "total_keys": len(all_keys),
            "found_keys": found_keys,
            "missing_keys": missing_keys,
            "key_count": {
                "found": len(found_keys),
                "missing": len(missing_keys)
            }
        }


# Convenience functions for common operations
def replace_keys(case_id: str, text: str, investigation_id: Optional[str] = None) -> str:
    """Quick function to replace keys with values."""
    service = KeyPlaceholderService(case_id)
    result = service.replace_keys_with_values(text, investigation_id)
    return result.processed_text


def prepare_for_llm(case_id: str, findings: Dict, investigation_id: Optional[str] = None) -> Tuple[str, Dict]:
    """Quick function to prepare findings for LLM prompt."""
    service = KeyPlaceholderService(case_id)
    return service.prepare_prompt_with_keys(findings, investigation_id)


def html_with_keys(case_id: str, text: str, investigation_id: Optional[str] = None) -> str:
    """Quick function to generate HTML with key hover tooltips."""
    service = KeyPlaceholderService(case_id)
    return service.generate_html_with_hover_keys(text, investigation_id)

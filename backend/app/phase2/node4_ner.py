"""
Node 4: NER Tagging & Fallback Validation
Named Entity Recognition with RE2 regex validation
"""

import re
from typing import Dict, Any, List, Optional
from app.core.logging import logger

# RE2-compatible regex patterns (Python re is RE2-compatible for most patterns)
IP_PATTERN = re.compile(r'\b(?:\d{1,3}\.){3}\d{1,3}\b')
EMAIL_PATTERN = re.compile(r'\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Z|a-z]{2,}\b')
URL_PATTERN = re.compile(r'https?://[^\s<>"{}|\\^`\[\]]+')
MAC_PATTERN = re.compile(r'\b([0-9A-Fa-f]{2}[:-]){5}([0-9A-Fa-f]{2})\b')
FILE_PATH_PATTERN = re.compile(r'[A-Za-z]:\\(?:[^\\/:*?"<>|\r\n]+\\)*[^\\/:*?"<>|\r\n]*|/(?:[^/]+/)*[^/]+')


def tag_entities(text: str) -> Dict[str, List[str]]:
    """
    Tag named entities in text.
    
    Args:
        text: Input text
    
    Returns:
        Dictionary of entity types and their values
    """
    tags = {
        "ip_addresses": [],
        "emails": [],
        "urls": [],
        "mac_addresses": [],
        "file_paths": [],
        "other": []
    }
    
    # Extract IPs
    ips = IP_PATTERN.findall(text)
    if ips:
        tags["ip_addresses"] = list(set(ips))
    
    # Extract emails
    emails = EMAIL_PATTERN.findall(text)
    if emails:
        tags["emails"] = list(set(emails))
    
    # Extract URLs
    urls = URL_PATTERN.findall(text)
    if urls:
        tags["urls"] = list(set(urls))
    
    # Extract MAC addresses
    macs = MAC_PATTERN.findall(text)
    if macs:
        tags["mac_addresses"] = [':'.join(m) for m in macs[:10]]
    
    # Extract file paths
    file_paths = FILE_PATH_PATTERN.findall(text)
    if file_paths:
        tags["file_paths"] = list(set(file_paths[:10]))
    
    return tags


def validate_regex_size(pattern: str, max_size: int = 2048) -> bool:
    """
    Check if regex pattern size is acceptable (RE2 compatibility).
    
    RE2 has limitations:
    - Pattern size < 2048 characters
    - No backreferences
    - No lookahead/lookbehind
    
    Args:
        pattern: Regex pattern string
        max_size: Maximum pattern size in characters (default 2048)
    
    Returns:
        True if pattern size is acceptable for RE2
    """
    if len(pattern) >= max_size:
        logger.warning(f"[Node4] Regex pattern size {len(pattern)} exceeds RE2 limit {max_size}")
        return False
    
    # Check for RE2-incompatible features
    re2_incompatible = [
        r'\(\?<',      # Named groups (lookbehind)
        r'\(\?=',      # Positive lookahead
        r'\(\?!',      # Negative lookahead
        r'\(\?<=',     # Positive lookbehind
        r'\(\?<!',     # Negative lookbehind
        r'\\\d+',      # Backreferences (\1, \2, etc.)
    ]
    
    for incompatible in re2_incompatible:
        if re.search(incompatible, pattern):
            logger.warning(f"[Node4] Regex pattern contains RE2-incompatible feature: {incompatible}")
            return False
    
    return True


def validate_all_regex_patterns() -> Dict[str, bool]:
    """
    Validate all NER regex patterns for RE2 compatibility.
    
    Returns:
        Dictionary of pattern names and validation status
    """
    patterns = {
        "IP_PATTERN": IP_PATTERN.pattern,
        "EMAIL_PATTERN": EMAIL_PATTERN.pattern,
        "URL_PATTERN": URL_PATTERN.pattern,
        "MAC_PATTERN": MAC_PATTERN.pattern,
        "FILE_PATH_PATTERN": FILE_PATH_PATTERN.pattern,
    }
    
    validation_results = {}
    for name, pattern in patterns.items():
        validation_results[name] = validate_regex_size(pattern)
        if not validation_results[name]:
            logger.error(f"[Node4] Pattern {name} failed RE2 validation")
    
    return validation_results


def neutralize_sqli(text: str) -> str:
    """
    Neutralize SQL injection attempts by parameterizing strings.
    
    Detects and neutralizes:
    - SQL keywords (SELECT, INSERT, UPDATE, DELETE, DROP, UNION, EXEC)
    - SQL operators (OR, AND, --, /*, */)
    - SQL functions (CONCAT, CHAR, ASCII, SUBSTRING)
    - Injection patterns (1=1, ' OR '1'='1, etc.)
    
    Args:
        text: Input text
    
    Returns:
        Neutralized text with SQLi patterns replaced
    """
    if not text:
        return text
    
    neutralized = text
    
    # SQL keywords (case-insensitive)
    sql_keywords = [
        'SELECT', 'INSERT', 'UPDATE', 'DELETE', 'DROP', 'CREATE', 'ALTER',
        'UNION', 'EXEC', 'EXECUTE', 'TRUNCATE', 'GRANT', 'REVOKE',
        'MERGE', 'CALL', 'DECLARE', 'FETCH', 'OPEN', 'CLOSE'
    ]
    
    for keyword in sql_keywords:
        # Replace whole word only (not part of other words)
        pattern = rf'\b{re.escape(keyword)}\b'
        neutralized = re.sub(pattern, f'<{keyword.lower()}>', neutralized, flags=re.IGNORECASE)
    
    # SQL operators and comments
    sql_operators = [
        (r'\bOR\b', '<or>'),
        (r'\bAND\b', '<and>'),
        (r'--.*', '<comment>'),  # SQL comment
        (r'/\*.*?\*/', '<comment>'),  # Multi-line comment
        (r';\s*$', '<semicolon>'),  # Statement terminator
    ]
    
    for pattern, replacement in sql_operators:
        neutralized = re.sub(pattern, replacement, neutralized, flags=re.IGNORECASE | re.DOTALL)
    
    # Common SQL injection patterns
    injection_patterns = [
        (r"'\s*OR\s*'1'\s*=\s*'1", '<sqli_pattern>'),
        (r"'\s*OR\s*'1'\s*=\s*'1'", '<sqli_pattern>'),
        (r"1\s*=\s*1", '<sqli_pattern>'),
        (r"'\s*OR\s*1\s*=\s*1", '<sqli_pattern>'),
        (r"UNION\s+SELECT", '<sqli_pattern>'),
        (r"';?\s*--", '<sqli_pattern>'),
        (r"'\s*;\s*DROP", '<sqli_pattern>'),
    ]
    
    for pattern, replacement in injection_patterns:
        neutralized = re.sub(pattern, replacement, neutralized, flags=re.IGNORECASE)
    
    # SQL functions that could be used in injection
    sql_functions = [
        'CONCAT', 'CHAR', 'ASCII', 'SUBSTRING', 'SUBSTR', 'LENGTH',
        'CAST', 'CONVERT', 'HEX', 'UNHEX', 'LOAD_FILE', 'INTO OUTFILE'
    ]
    
    for func in sql_functions:
        pattern = rf'\b{re.escape(func)}\s*\('
        neutralized = re.sub(pattern, f'<{func.lower()}>', neutralized, flags=re.IGNORECASE)
    
    # Log if neutralization occurred
    if neutralized != text:
        logger.warning(f"[Node4] SQLi neutralization applied: {len(text)} -> {len(neutralized)} chars")
    
    return neutralized


def process_ner_tagging(
    text: str,
    template: Optional[str] = None
) -> Dict[str, Any]:
    """
    Process text through NER tagging and validation pipeline.
    
    Flow:
    1. NER model guessing tags (entity extraction)
    2. RE2 Regex validation (< 2048 chars)
    3. Lock tags (if valid) OR Fallback logic
    4. SQLi neutralization
    
    Args:
        text: Input text
        template: Optional template for context
    
    Returns:
        {
            "tags": dict,
            "validated": bool,
            "fallback": bool,
            "neutralized": str,
            "regex_valid": bool
        }
    """
    # Step 1: NER Model - Tag entities
    tags = tag_entities(text)
    logger.debug(f"[Node4] NER model extracted: IPs={len(tags['ip_addresses'])}, "
                 f"Emails={len(tags['emails'])}, URLs={len(tags['urls'])}")
    
    # Step 2: RE2 Regex Validation (< 2048)
    regex_valid = True
    use_fallback = False
    
    if template:
        # Validate template regex size
        regex_valid = validate_regex_size(template, max_size=2048)
        
        if not regex_valid:
            use_fallback = True
            logger.warning(f"[Node4] Template regex validation failed (size or RE2 incompatible), using fallback")
    
    # Validate all NER regex patterns on startup (once)
    if not hasattr(process_ner_tagging, '_patterns_validated'):
        validation_results = validate_all_regex_patterns()
        if not all(validation_results.values()):
            logger.error(f"[Node4] Some NER regex patterns failed validation: {validation_results}")
        process_ner_tagging._patterns_validated = True
    
    # Step 3: Decision - Lock Tags OR Fallback
    if use_fallback:
        # Fallback Logic: Tag as suspicious or unknown
        if len(text) > 1000:
            tags["other"].append("Suspicious_Length")
            logger.warning(f"[Node4] Fallback: Tagged as Suspicious_Length (text length: {len(text)})")
        else:
            tags["other"].append("Unknown_String")
            logger.warning(f"[Node4] Fallback: Tagged as Unknown_String")
        tags_locked = False
    else:
        # Lock Tags: IP, Email, URL, etc.
        tags_locked = any([
            tags["ip_addresses"],
            tags["emails"],
            tags["urls"],
            tags["mac_addresses"]
        ])
        
        if tags_locked:
            logger.debug(f"[Node4] Tags locked: {[k for k, v in tags.items() if v and k != 'other']}")
        else:
            logger.debug(f"[Node4] No entities found to lock")
    
    # Step 4: SQLi Neutralization (Parameterized Strings)
    neutralized = neutralize_sqli(text)
    
    logger.debug(
        f"[Node4] NER tagging complete: "
        f"IPs={len(tags['ip_addresses'])}, "
        f"Emails={len(tags['emails'])}, "
        f"URLs={len(tags['urls'])}, "
        f"locked={tags_locked}, "
        f"fallback={use_fallback}, "
        f"regex_valid={regex_valid}"
    )
    
    return {
        "tags": tags,
        "validated": tags_locked,
        "fallback": use_fallback,
        "neutralized": neutralized,
        "regex_valid": regex_valid
    }


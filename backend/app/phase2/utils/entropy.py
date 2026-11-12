"""
Shannon Entropy Calculation
Used for detecting obfuscated data (high entropy = likely encoded/encrypted)
"""

import math
from collections import Counter


def calculate_shannon_entropy(data: str | bytes) -> float:
    """
    Calculate Shannon entropy of a string or bytes.
    
    H(X) = -Σ P(x) * log2(P(x))
    
    Returns:
        Entropy value in bits per byte (0-8.0)
        - 0 = completely predictable
        - 8.0 = maximum randomness (uniform distribution)
        - > 7.2 = likely obfuscated/encrypted
    """
    if isinstance(data, str):
        data = data.encode('utf-8', errors='ignore')
    
    if not data:
        return 0.0
    
    length = len(data)
    if length == 0:
        return 0.0
    
    counts = Counter(data)
    entropy = 0.0
    
    for count in counts.values():
        probability = count / length
        if probability > 0:
            entropy -= probability * math.log2(probability)
    
    return entropy


def is_high_entropy(data: str | bytes, threshold: float = 7.2) -> bool:
    """
    Check if data has high entropy (likely obfuscated).
    
    Args:
        data: String or bytes to check
        threshold: Entropy threshold (default 7.2 bits/byte)
    
    Returns:
        True if entropy exceeds threshold
    """
    entropy = calculate_shannon_entropy(data)
    return entropy >= threshold


def detect_obfuscation(data: str | bytes) -> dict:
    """
    Detect if data is obfuscated and suggest decoder type.
    
    Returns:
        {
            "is_obfuscated": bool,
            "entropy": float,
            "suggested_decoders": list[str]  # ["url", "base64", "hex"]
        }
    """
    entropy = calculate_shannon_entropy(data)
    is_obf = entropy >= 7.2
    
    suggested = []
    if is_obf:
        data_str = data.decode('utf-8', errors='ignore') if isinstance(data, bytes) else data
        
        if '%' in data_str and len(data_str) > 10:
            suggested.append("url")
        
        if data_str.replace('+', '').replace('/', '').replace('=', '').isalnum() and len(data_str) % 4 == 0:
            suggested.append("base64")
        
        if all(c in '0123456789abcdefABCDEF' for c in data_str.replace(' ', '').replace(':', '')):
            suggested.append("hex")
    
    return {
        "is_obfuscated": is_obf,
        "entropy": entropy,
        "suggested_decoders": suggested
    }









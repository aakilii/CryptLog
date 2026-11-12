"""
Recursive De-obfuscation Decoders
URL → Base64 → Hex decoding chain
"""

import base64
import urllib.parse
from typing import Optional


def decode_url(encoded: str) -> Optional[str]:
    """Decode URL-encoded string."""
    try:
        return urllib.parse.unquote(encoded)
    except Exception:
        return None


def decode_base64(encoded: str) -> Optional[str]:
    """Decode Base64 string."""
    try:
        decoded_bytes = base64.b64decode(encoded, validate=True)
        return decoded_bytes.decode('utf-8', errors='ignore')
    except Exception:
        return None


def decode_hex(encoded: str) -> Optional[str]:
    """Decode hexadecimal string."""
    try:
        hex_clean = encoded.replace(' ', '').replace(':', '').replace('-', '')
        decoded_bytes = bytes.fromhex(hex_clean)
        return decoded_bytes.decode('utf-8', errors='ignore')
    except Exception:
        return None


def recursive_decode(
    data: str,
    max_depth: int = 5,
    current_depth: int = 0,
    trace: Optional[list] = None
) -> tuple[Optional[str], list]:
    """
    Recursively decode obfuscated data.
    
    Decoder chain: URL → Base64 → Hex
    
    Args:
        data: Input string to decode
        max_depth: Maximum recursion depth (default 5)
        current_depth: Current recursion depth
        trace: List of decoding steps taken
    
    Returns:
        (decoded_data, trace_array)
    """
    if trace is None:
        trace = []
    
    if current_depth >= max_depth:
        trace.append({"step": current_depth, "action": "max_depth_reached", "result": None})
        return None, trace
    
    if not data or not isinstance(data, str):
        return data, trace
    
    original = data
    
    decoders = [
        ("url", decode_url),
        ("base64", decode_base64),
        ("hex", decode_hex),
    ]
    
    for decoder_name, decoder_func in decoders:
        decoded = decoder_func(data)
        if decoded and decoded != data and len(decoded) > 0:
            trace.append({
                "step": current_depth + 1,
                "decoder": decoder_name,
                "input_length": len(data),
                "output_length": len(decoded),
                "success": True
            })
            
            result, final_trace = recursive_decode(
                decoded,
                max_depth=max_depth,
                current_depth=current_depth + 1,
                trace=trace
            )
            
            if result is not None:
                return result, final_trace
    
    if current_depth == 0:
        trace.append({
            "step": 0,
            "action": "no_decoding_needed",
            "result": "original"
        })
    
    return original, trace


def decode_with_trace(data: str, max_depth: int = 5) -> dict:
    """
    Decode data and return full trace.
    
    Returns:
        {
            "original": str,
            "decoded": str | None,
            "trace": list[dict],
            "depth": int
        }
    """
    decoded, trace = recursive_decode(data, max_depth=max_depth)
    
    return {
        "original": data,
        "decoded": decoded if decoded != data else None,
        "trace": trace,
        "depth": len([t for t in trace if t.get("decoder")])
    }









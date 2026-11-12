"""
Node 2: Recursive De-obfuscation (Decoder Ring)
Detect and decode obfuscated data using Shannon entropy
"""

from typing import Optional
from app.core.logging import logger
from app.phase2.utils.entropy import is_high_entropy, detect_obfuscation
from app.phase2.utils.decoders import decode_with_trace


MAX_RECURSION_DEPTH = 5
ENTROPY_THRESHOLD = 7.2


def process_deobfuscation(data: str | bytes) -> dict:
    """
    Process data through recursive de-obfuscation pipeline.
    
    Args:
        data: Input data (string or bytes)
    
    Returns:
        {
            "original": str,
            "decoded": str | None,
            "is_obfuscated": bool,
            "entropy": float,
            "trace": list[dict],
            "depth": int
        }
    """
    if isinstance(data, bytes):
        data = data.decode('utf-8', errors='ignore')
    
    if not data:
        return {
            "original": "",
            "decoded": None,
            "is_obfuscated": False,
            "entropy": 0.0,
            "trace": [],
            "depth": 0
        }
    
    obfuscation_info = detect_obfuscation(data)
    is_obf = obfuscation_info["is_obfuscated"]
    
    if not is_obf:
        logger.debug(f"[Node2] Low entropy detected, skipping decoder loop")
        return {
            "original": data,
            "decoded": None,
            "is_obfuscated": False,
            "entropy": obfuscation_info["entropy"],
            "trace": [{"step": 0, "action": "low_entropy", "skipped": True}],
            "depth": 0
        }
    
    logger.debug(
        f"[Node2] High entropy detected ({obfuscation_info['entropy']:.2f} bits/byte), "
        f"entering decoder loop. Suggested: {obfuscation_info['suggested_decoders']}"
    )
    
    decode_result = decode_with_trace(data, max_depth=MAX_RECURSION_DEPTH)
    
    if decode_result["decoded"]:
        logger.info(
            f"[Node2] Decoding successful: depth={decode_result['depth']}, "
            f"steps={len(decode_result['trace'])}"
        )
    else:
        logger.debug(f"[Node2] No decoding applied or failed")
    
    return {
        "original": decode_result["original"],
        "decoded": decode_result["decoded"],
        "is_obfuscated": is_obf,
        "entropy": obfuscation_info["entropy"],
        "trace": decode_result["trace"],
        "depth": decode_result["depth"]
    }


import hashlib
import re

def compute_simhash(text: str) -> str:
    """Computes a 64-bit SimHash hex string for text deduplication."""
    tokens = re.findall(r"\w{3,}", text.lower())
    if not tokens:
        return "0" * 16

    v = [0] * 64
    for token in tokens:
        h = int(hashlib.md5(token.encode("utf-8")).hexdigest(), 16)
        for i in range(64):
            bit = (h >> i) & 1
            v[i] += 1 if bit else -1

    fingerprint = 0
    for i in range(64):
        if v[i] > 0:
            fingerprint |= (1 << i)

    return f"{fingerprint:016x}"

def hamming_distance(hash1: str, hash2: str) -> int:
    """
    Returns number of differing bits between two 64-bit hex SimHashes.
    Returns 64 (maximum difference) if either hash is invalid or unparseable.
    """
    try:
        if not hash1 or not hash2:
            return 64
        val1 = int(str(hash1).strip(), 16)
        val2 = int(str(hash2).strip(), 16)
        diff = val1 ^ val2
        return bin(diff).count("1")
    except (ValueError, TypeError):
        return 64

def are_near_duplicates(hash1: str, hash2: str, max_distance: int = 3) -> bool:
    """Returns True if two documents have Hamming distance <= max_distance."""
    try:
        return hamming_distance(hash1, hash2) <= max_distance
    except Exception:
        return False

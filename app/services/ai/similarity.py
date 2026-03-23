import math
import re
from collections import Counter


def haversine_meters(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    radius = 6371000
    phi1, phi2 = math.radians(lat1), math.radians(lat2)
    d_phi = math.radians(lat2 - lat1)
    d_lambda = math.radians(lon2 - lon1)
    a = math.sin(d_phi / 2) ** 2 + math.cos(phi1) * math.cos(phi2) * math.sin(d_lambda / 2) ** 2
    return 2 * radius * math.atan2(math.sqrt(a), math.sqrt(1 - a))


def tokenize(text: str) -> list[str]:
    return re.findall(r"[a-z0-9]+", text.lower())


def text_similarity(a: str, b: str) -> float:
    a_tokens = tokenize(a)
    b_tokens = tokenize(b)
    if not a_tokens or not b_tokens:
        return 0.0

    a_count = Counter(a_tokens)
    b_count = Counter(b_tokens)
    common = sum((a_count & b_count).values())
    total = sum((a_count | b_count).values())
    return common / total if total else 0.0

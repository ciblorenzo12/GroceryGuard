from __future__ import annotations
import time
from dataclasses import dataclass
from typing import Dict, List, Tuple

@dataclass
class RateDecision:
    allowed: bool
    retry_after_s: int

class MinuteBucketLimiter:
    """
    I had tracked requests per key (usually IP) and blocked if they exceeded the limit per minute.
    This had implemented basic rate limiting so people didn't spam the API.
    """
    def __init__(self, max_per_minute: int) -> None:
        self.max_per_minute = max_per_minute
        self._buckets: Dict[str, List[float]] = {}

    def check(self, key: str) -> RateDecision:
        now = time.time()
        bucket = self._buckets.setdefault(key, [])
        bucket[:] = [t for t in bucket if now - t < 60.0]

        if len(bucket) >= self.max_per_minute:
            oldest = min(bucket) if bucket else now
            retry = max(1, int(60 - (now - oldest)))
            return RateDecision(False, retry)

        bucket.append(now)
        return RateDecision(True, 0)
from __future__ import annotations

import threading
import time


class RangeCountGuard:
    """Deduplicate rapid range requests from one download action."""

    def __init__(self, window_seconds: int = 5) -> None:
        self.window_seconds = max(1, int(window_seconds))
        self._recent: dict[tuple[str, str, str], float] = {}
        self._lock = threading.Lock()

    def should_count(self, filename: str, client_id: str, user_agent: str) -> bool:
        key = (filename, client_id, user_agent)
        now = time.monotonic()

        with self._lock:
            last_seen = self._recent.get(key)
            if last_seen is not None and (now - last_seen) < self.window_seconds:
                return False

            self._recent[key] = now
            self._prune(now)
            return True

    def _prune(self, now: float) -> None:
        threshold = self.window_seconds * 3
        stale_keys = [
            key for key, ts in self._recent.items() if (now - ts) > threshold
        ]
        for key in stale_keys:
            self._recent.pop(key, None)


import threading
import time


class TTLCache:
    """Thread-safe in-memory TTL cache for hot read-mostly reference and summary queries."""

    def __init__(self, max_entries=256):
        self._lock = threading.Lock()
        self._store = {}
        self._max_entries = max_entries

    def get(self, key):
        now = time.monotonic()
        with self._lock:
            entry = self._store.get(key)
            if entry is None:
                return None
            expires_at, value = entry
            if now >= expires_at:
                self._store.pop(key, None)
                return None
            return value

    def set(self, key, value, ttl_seconds=20):
        expires_at = time.monotonic() + max(1, int(ttl_seconds))
        with self._lock:
            if len(self._store) >= self._max_entries:
                now = time.monotonic()
                expired = [k for k, (exp, _) in self._store.items() if now >= exp]
                for k in expired:
                    self._store.pop(k, None)
                if len(self._store) >= self._max_entries:
                    self._store.clear()
            self._store[key] = (expires_at, value)
        return value

    def invalidate_prefix(self, prefix=None):
        with self._lock:
            if not prefix:
                self._store.clear()
                return
            for key in [k for k in self._store if k.startswith(prefix)]:
                self._store.pop(key, None)


app_cache = TTLCache(max_entries=256)

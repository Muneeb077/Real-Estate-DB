import json
import logging
import threading
import time

from flask_limiter import Limiter
from flask_limiter.util import get_remote_address

limiter = Limiter(key_func=get_remote_address, default_limits=["300 per minute"])
log = logging.getLogger(__name__)


class Cache:
    """
    Tiny JSON cache. Shared across API processes on Redis; without REDIS_URL it
    falls back to a small per-process TTL dict, so development needs only MySQL.
    """

    LOCAL_MAX = 2000

    def __init__(self):
        self.redis = None
        self.ttl = 60
        self._local = {}
        self._versions = {}
        self._lock = threading.Lock()

    def init_app(self, app):
        self.ttl = app.config["CACHE_TTL"]
        if app.config.get("REDIS_URL"):
            import redis
            self.redis = redis.Redis.from_url(app.config["REDIS_URL"])

    def get(self, key):
        if not self.redis:
            hit = self._local.get(key)
            if hit and hit[0] > time.monotonic():
                return json.loads(hit[1])
            return None
        try:
            raw = self.redis.get(key)
            return json.loads(raw) if raw else None
        except Exception:
            log.warning("cache get failed", exc_info=True)
            return None

    def set(self, key, value, ttl=None):
        if not self.redis:
            with self._lock:
                if len(self._local) >= self.LOCAL_MAX:
                    self._local.clear()
                self._local[key] = (time.monotonic() + (ttl or self.ttl), json.dumps(value, default=str))
            return
        if self.redis:
            try:
                self.redis.setex(key, ttl or self.ttl, json.dumps(value, default=str))
            except Exception:
                log.warning("cache set failed", exc_info=True)

    def bump(self, namespace):
        """
        Invalidates a namespace by bumping its version (keys embed the version).
        """
        if not self.redis:
            self._versions[namespace] = self._versions.get(namespace, 0) + 1
            return
        if self.redis:
            try:
                self.redis.incr(f"v:{namespace}")
            except Exception:
                log.warning("cache bump failed", exc_info=True)

    def version(self, namespace):
        if not self.redis:
            return self._versions.get(namespace, 0)
        try:
            return int(self.redis.get(f"v:{namespace}") or 0)
        except Exception:
            return 0


cache = Cache()

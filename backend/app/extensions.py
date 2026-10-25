import json
import logging

from flask_limiter import Limiter
from flask_limiter.util import get_remote_address

limiter = Limiter(key_func=get_remote_address, default_limits=["300 per minute"])
log = logging.getLogger(__name__)


class Cache:
    """
    Tiny JSON cache on Redis. Without REDIS_URL it is a no-op, so the app works
    with only MySQL in development.
    """

    def __init__(self):
        self.redis = None
        self.ttl = 60

    def init_app(self, app):
        self.ttl = app.config["CACHE_TTL"]
        if app.config.get("REDIS_URL"):
            import redis
            self.redis = redis.Redis.from_url(app.config["REDIS_URL"])

    def get(self, key):
        if not self.redis:
            return None
        try:
            raw = self.redis.get(key)
            return json.loads(raw) if raw else None
        except Exception:
            log.warning("cache get failed", exc_info=True)
            return None

    def set(self, key, value, ttl=None):
        if self.redis:
            try:
                self.redis.setex(key, ttl or self.ttl, json.dumps(value, default=str))
            except Exception:
                log.warning("cache set failed", exc_info=True)

    def bump(self, namespace):
        """
        Invalidates a namespace by bumping its version (keys embed the version).
        """
        if self.redis:
            try:
                self.redis.incr(f"v:{namespace}")
            except Exception:
                log.warning("cache bump failed", exc_info=True)

    def version(self, namespace):
        if not self.redis:
            return 0
        try:
            return int(self.redis.get(f"v:{namespace}") or 0)
        except Exception:
            return 0


cache = Cache()

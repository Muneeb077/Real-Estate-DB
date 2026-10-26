import os


def _bool(name, default=False):
    return os.environ.get(name, str(default)).lower() in ("1", "true", "yes")


class Config:
    """
    All configuration comes from the environment (see .env.example).
    Nothing secret is committed to the repository.
    """

    ENV = os.environ.get("APP_ENV", "production")
    SECRET_KEY = os.environ.get("SECRET_KEY")
    DATABASE_URL = os.environ.get("DATABASE_URL")
    DATABASE_REPLICA_URL = os.environ.get("DATABASE_REPLICA_URL")
    DB_SSL_CA = os.environ.get("DB_SSL_CA")
    DB_SSL_REQUIRED = _bool("DB_SSL_REQUIRED")
    DB_POOL_SIZE = int(os.environ.get("DB_POOL_SIZE", 10))
    REDIS_URL = os.environ.get("REDIS_URL")
    BACKUP_DATABASE_URL = os.environ.get("BACKUP_DATABASE_URL")  # read-only account used by mysqldump

    # Envelope encryption: KEK_KEYS="v1:<base64 32 bytes>,v2:<...>", KEK_ACTIVE="v2"
    KEK_KEYS = os.environ.get("KEK_KEYS", "")
    KEK_ACTIVE = os.environ.get("KEK_ACTIVE", "v1")
    BLIND_INDEX_KEY = os.environ.get("BLIND_INDEX_KEY", "")

    JWT_ACCESS_TTL = int(os.environ.get("JWT_ACCESS_TTL", 900))
    REFRESH_TTL_DAYS = int(os.environ.get("REFRESH_TTL_DAYS", 14))
    COOKIE_SECURE = _bool("COOKIE_SECURE", True)
    ADMIN_REQUIRE_MFA = _bool("ADMIN_REQUIRE_MFA", True)
    REQUIRE_VERIFIED_EMAIL = _bool("REQUIRE_VERIFIED_EMAIL", True)

    FRONTEND_URL = os.environ.get("FRONTEND_URL", "http://localhost:3000")
    MEDIA_URL = os.environ.get("MEDIA_URL", "/media")
    UPLOAD_DIR = os.environ.get("UPLOAD_DIR") or os.path.join(os.path.dirname(__file__), "..", "uploads")
    BACKUP_DIR = os.environ.get("BACKUP_DIR") or os.path.join(os.path.dirname(__file__), "..", "backups")
    MAX_UPLOAD_MB = int(os.environ.get("MAX_UPLOAD_MB", 8))
    S3_BUCKET = os.environ.get("S3_BUCKET")
    S3_ENDPOINT_URL = os.environ.get("S3_ENDPOINT_URL")
    S3_PUBLIC_URL = os.environ.get("S3_PUBLIC_URL")

    SMTP_URL = os.environ.get("SMTP_URL")  # unset: emails are logged to the console
    MAIL_FROM = os.environ.get("MAIL_FROM", "HomeNest <no-reply@homenest.local>")
    STRIPE_SECRET_KEY = os.environ.get("STRIPE_SECRET_KEY")
    STRIPE_WEBHOOK_SECRET = os.environ.get("STRIPE_WEBHOOK_SECRET")
    SENTRY_DSN = os.environ.get("SENTRY_DSN")
    RATELIMIT_STORAGE_URI = os.environ.get("REDIS_URL", "memory://")
    CACHE_TTL = int(os.environ.get("CACHE_TTL", 60))

    TESTING = False

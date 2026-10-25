import logging
import os

from dotenv import load_dotenv
from flask import Flask

load_dotenv()

from . import db, errors
from .config import Config
from .extensions import cache, limiter
from .security import crypto
from .security.rbac import authenticate_request


def _check_config(app):
    missing = [k for k in ("SECRET_KEY", "DATABASE_URL", "KEK_KEYS", "BLIND_INDEX_KEY") if not app.config.get(k)]
    if missing:
        raise RuntimeError(f"Missing required configuration: {', '.join(missing)} (see .env.example)")
    if len(app.config["SECRET_KEY"]) < 32:
        raise RuntimeError("SECRET_KEY must be at least 32 characters")


def create_app(overrides=None):
    app = Flask(__name__)
    app.config.from_object(Config)
    if overrides:
        app.config.update(overrides)
    _check_config(app)
    app.config["MAX_CONTENT_LENGTH"] = app.config["MAX_UPLOAD_MB"] * 1024 * 1024

    logging.basicConfig(level=logging.INFO, format='{"level":"%(levelname)s","logger":"%(name)s","msg":"%(message)s"}')
    if app.config.get("SENTRY_DSN"):
        import sentry_sdk
        sentry_sdk.init(dsn=app.config["SENTRY_DSN"], send_default_pii=False)

    db.init_app(app)
    crypto.init_app(app)
    cache.init_app(app)
    app.config["RATELIMIT_ENABLED"] = not app.config.get("TESTING") or app.config.get("RATELIMIT_ENABLED", False)
    limiter.init_app(app)
    errors.register(app)
    app.before_request(authenticate_request)

    from .api import register_blueprints
    register_blueprints(app)

    if app.config["ENV"] == "production" and not app.config.get("TESTING"):
        from flask_talisman import Talisman
        # API responses are JSON; the strict CSP mainly protects anything served directly.
        Talisman(app, force_https=False, content_security_policy={"default-src": "'none'"},
                 strict_transport_security=True, strict_transport_security_max_age=31536000)
    if os.environ.get("PROMETHEUS_METRICS") == "1":
        from prometheus_flask_exporter import PrometheusMetrics
        PrometheusMetrics(app, path="/metrics")
    return app

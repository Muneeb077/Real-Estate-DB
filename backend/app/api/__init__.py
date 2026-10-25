from flask import Blueprint, jsonify

from .. import db

health = Blueprint("health", __name__)


@health.get("/api/v1/health")
def healthcheck():
    db.scalar("SELECT 1")
    return jsonify(status="ok")


def register_blueprints(app):
    from . import auth, host, interactions, listings, me, stays

    app.register_blueprint(health)
    for module in (listings, auth, me, interactions, host, stays):
        app.register_blueprint(module.bp)

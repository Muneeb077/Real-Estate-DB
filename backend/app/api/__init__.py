import os

from flask import Blueprint, current_app, jsonify, send_from_directory

from .. import db

health = Blueprint("health", __name__)


@health.get("/media/<path:path>")
def media(path):
    # Local-disk uploads in development; production serves these from S3/CDN.
    return send_from_directory(os.path.abspath(current_app.config["UPLOAD_DIR"]), path, max_age=31536000)


@health.get("/api/v1/health")
def healthcheck():
    db.scalar("SELECT 1")
    return jsonify(status="ok")


def register_blueprints(app):
    from . import admin, auth, host, interactions, listings, me, stays

    app.register_blueprint(health)
    for module in (listings, auth, me, interactions, host, stays, admin):
        app.register_blueprint(module.bp)

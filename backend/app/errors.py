import logging

from flask import jsonify
from pydantic import ValidationError
from sqlalchemy.exc import DBAPIError
from werkzeug.exceptions import HTTPException

log = logging.getLogger(__name__)


class ApiError(Exception):
    def __init__(self, status, code, message, details=None):
        super().__init__(message)
        self.status, self.code, self.message, self.details = status, code, message, details


def _payload(code, message, details=None):
    body = {"error": {"code": code, "message": message}}
    if details:
        body["error"]["details"] = details
    return body


def register(app):
    @app.errorhandler(ApiError)
    def api_error(e):
        return jsonify(_payload(e.code, e.message, e.details)), e.status

    @app.errorhandler(ValidationError)
    def validation_error(e):
        details = [{"field": ".".join(str(p) for p in err["loc"]), "message": err["msg"]} for err in e.errors()]
        return jsonify(_payload("validation_error", "Some fields are invalid.", details)), 422

    @app.errorhandler(DBAPIError)
    def db_error(e):
        code = e.orig.args[0] if e.orig is not None and e.orig.args else None
        if code == 1644:
            # SIGNAL SQLSTATE '45000' from a stored procedure or trigger: a business rule
            # violation whose message was written for end users.
            return jsonify(_payload("rule_violation", e.orig.args[1])), 409
        if code == 1062:
            return jsonify(_payload("conflict", "That record already exists.")), 409
        if code == 3819:
            return jsonify(_payload("validation_error", "A value is out of the allowed range.")), 422
        log.exception("Database error")
        return jsonify(_payload("server_error", "Something went wrong.")), 500

    @app.errorhandler(HTTPException)
    def http_error(e):
        return jsonify(_payload(e.name.lower().replace(" ", "_"), e.description)), e.code

    @app.errorhandler(Exception)
    def unhandled(e):
        # Never leak internals: log the stack trace, return a generic message.
        log.exception("Unhandled error")
        return jsonify(_payload("server_error", "Something went wrong.")), 500

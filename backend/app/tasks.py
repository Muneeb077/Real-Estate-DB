"""
Background jobs. With REDIS_URL set, jobs go to an RQ queue processed by
`python worker.py`; without it they run inline so development needs only MySQL.
Jobs receive plain data (never decrypted secrets beyond what they must send).
"""
import logging

from flask import current_app

log = logging.getLogger("tasks")


def enqueue(func, *args, **kwargs):
    redis_url = current_app.config.get("REDIS_URL")
    if redis_url and not current_app.config.get("TESTING"):
        from redis import Redis
        from rq import Queue
        Queue("default", connection=Redis.from_url(redis_url)).enqueue(func, *args, **kwargs)
        return
    func(*args, **kwargs)


def _app():
    from . import create_app
    return create_app()


def send_email_job(to, subject, text):
    from .mail import send_email
    try:
        current_app.config  # inside an app context already (inline mode)
        send_email(to, subject, text)
    except RuntimeError:
        with _app().app_context():
            send_email(to, subject, text)

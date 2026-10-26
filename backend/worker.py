"""
Background worker: processes the RQ queue (emails, backups) when REDIS_URL is set.

    python worker.py
"""
from redis import Redis
from rq import Worker

from app import create_app

app = create_app()

if __name__ == "__main__":
    with app.app_context():
        Worker(["default"], connection=Redis.from_url(app.config["REDIS_URL"])).work()

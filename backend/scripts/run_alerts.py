"""
Scheduler entry point: run saved-search alerts once (cron), or every hour with --loop.
"""
import os
import sys
import time

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from app import create_app
from app.alerts import run_saved_search_alerts

if __name__ == "__main__":
    app = create_app()
    while True:
        with app.app_context():
            run_saved_search_alerts()
        if "--loop" not in sys.argv:
            break
        time.sleep(3600)

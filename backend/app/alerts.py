"""
Saved-search alerts: for each saved search with alerts on, run it through the same
SearchListings procedure the site uses and email listings published since the
last alert. Run hourly by the scheduler (scripts/run_alerts.py).
"""
import json
import logging

from flask import current_app

from . import db
from .api.common import fulltext_query
from .notify import notify
from .security import crypto
from .tasks import enqueue, send_email_job

log = logging.getLogger("alerts")


def run_saved_search_alerts():
    sent = 0
    searches = db.query("""SELECT s.id, s.user_id, s.name, s.query, s.last_notified_at, u.email_enc
                           FROM saved_searches s JOIN users u ON u.id = s.user_id
                           WHERE s.alerts = TRUE AND u.status = 'active'""")
    for s in searches:
        q = json.loads(s["query"])
        rows = db.call("SearchListings", [
            fulltext_query(q.get("q")), q.get("mode"), q.get("type"), q.get("city"), q.get("min_price"),
            q.get("max_price"), q.get("beds"), q.get("baths"), q.get("guests"), q.get("amenities"),
            None, None, None, None, None, None, None, None, None, "newest", None, None, 10,
        ], read=True)
        fresh = [r for r in rows if r["published_at"] > (s["last_notified_at"] or "")]
        if fresh:
            front = current_app.config["FRONTEND_URL"]
            lines = "\n".join(f"- {r['title']} ({r['city']}): {front}/listings/{r['public_id']}" for r in fresh)
            email = crypto.decrypt(s["email_enc"], "users.email")
            enqueue(send_email_job, email, f"New homes for \"{s['name']}\"",
                    f"{len(fresh)} new listing(s) match your saved search:\n\n{lines}")
            notify(s["user_id"], "saved_search", f"{len(fresh)} new listing(s) for \"{s['name']}\"", "/wishlists")
            sent += 1
        db.execute("UPDATE saved_searches SET last_notified_at = NOW() WHERE id = :id", {"id": s["id"]})
    log.info("saved-search alerts sent: %s", sent)
    return sent

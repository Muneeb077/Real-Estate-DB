from . import db


def notify(user_id, kind, title, link=None, conn=None):
    db.execute("INSERT INTO notifications (user_id, kind, title, link) VALUES (:u, :k, :t, :l)",
               {"u": user_id, "k": kind, "t": title[:200], "l": link}, conn=conn)

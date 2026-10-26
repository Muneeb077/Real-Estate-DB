"""
Transactional email. With SMTP_URL unset (development) messages are written to
the log instead, so verification/reset links can be copied from the API output.
"""
import logging
import smtplib
import ssl
from email.message import EmailMessage
from urllib.parse import urlparse

from flask import current_app

log = logging.getLogger("mail")


def send_email(to, subject, text, smtp_url=None, sender=None):
    smtp_url = smtp_url if smtp_url is not None else current_app.config.get("SMTP_URL")
    sender = sender or current_app.config["MAIL_FROM"]
    if not smtp_url:
        log.info("EMAIL to=%s subject=%s\n%s", to, subject, text)
        return
    msg = EmailMessage()
    msg["From"], msg["To"], msg["Subject"] = sender, to, subject
    msg.set_content(text)
    u = urlparse(smtp_url)  # smtp+starttls://user:pass@host:587
    with smtplib.SMTP(u.hostname, u.port or 587, timeout=15) as s:
        s.starttls(context=ssl.create_default_context())
        if u.username:
            s.login(u.username, u.password)
        s.send_message(msg)

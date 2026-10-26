import os

from werkzeug.middleware.proxy_fix import ProxyFix

from app import create_app

app = create_app()
# Behind Nginx: trust exactly one proxy hop for the client IP and scheme, so rate
# limits, lockout records and audit IPs see the real client, not the proxy.
if os.environ.get("BEHIND_PROXY", "1") == "1":
    app.wsgi_app = ProxyFix(app.wsgi_app, x_for=1, x_proto=1, x_host=1)

if __name__ == "__main__":
    app.run(port=5050)

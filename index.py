import os
import sys

for p in [
    os.getcwd(),
    os.path.dirname(os.path.abspath(__file__))
]:
    if p and p not in sys.path:
        sys.path.insert(0, p)

os.environ['VERCEL'] = '1'

from app import app, db

# Enable ProxyFix for reverse proxy
try:
    from werkzeug.middleware.proxy_fix import ProxyFix
    app.wsgi_app = ProxyFix(app.wsgi_app, x_for=1, x_proto=1, x_host=1, x_prefix=1)
except Exception:
    pass

handler = app

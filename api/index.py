import os
import sys

# Ensure all potential root directories are on Python path
for p in [
    os.getcwd(),
    os.path.dirname(os.path.abspath(__file__)),
    os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
]:
    if p and p not in sys.path:
        sys.path.insert(0, p)

os.environ['VERCEL'] = '1'

try:
    from app import app, db
except Exception:
    import app as _app_pkg
    app = getattr(_app_pkg, 'app', None) or _app_pkg.create_app()
    db = _app_pkg.db

# Enable ProxyFix for Vercel reverse proxy
try:
    from werkzeug.middleware.proxy_fix import ProxyFix
    app.wsgi_app = ProxyFix(app.wsgi_app, x_for=1, x_proto=1, x_host=1, x_prefix=1)
except Exception:
    pass

# Export both 'app' and 'handler' for Vercel Python runtime
handler = app

@app.route('/healthz')
def healthz():
    return {"status": "ok", "service": "smart-civic-complaint-system"}

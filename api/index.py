import os
import sys

# Ensure application base directory is in sys.path
project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if project_root not in sys.path:
    sys.path.insert(0, project_root)

# Set VERCEL environment variable flag
os.environ['VERCEL'] = '1'

from app import create_app, db

config_name = 'production' if os.environ.get('VERCEL_ENV') == 'production' else 'development'
app = create_app(config_name)

# Enable ProxyFix so redirects and cookies work seamlessly behind Vercel reverse proxy
try:
    from werkzeug.middleware.proxy_fix import ProxyFix
    app.wsgi_app = ProxyFix(app.wsgi_app, x_for=1, x_proto=1, x_host=1, x_prefix=1)
except Exception:
    pass

# Lazy database initialization on first request
_db_ready = False

@app.before_request
def setup_database_if_needed():
    global _db_ready
    if not _db_ready:
        try:
            with app.app_context():
                db.create_all()
                from app.models.user import User
                if not User.query.filter_by(role='admin').first():
                    from app.services.seed_service import seed_all
                    seed_all()
        except Exception as e:
            app.logger.warning(f"Lazy DB init note: {e}")
        _db_ready = True

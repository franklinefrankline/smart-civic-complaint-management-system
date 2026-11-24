import os
import sys

# Ensure project root directory is on the python module search path
project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if project_root not in sys.path:
    sys.path.insert(0, project_root)

from app import create_app, db
from app.models.user import User

app = create_app('production' if os.environ.get('VERCEL_ENV') == 'production' else 'development')

# Auto-initialize database tables and seed if running for the first time
with app.app_context():
    try:
        db.create_all()
        # Seed default users/departments if newly created or empty
        if not User.query.filter_by(role='admin').first():
            from run import seed_db
            seed_db()
    except Exception as e:
        print(f"Vercel DB initialization note: {e}")

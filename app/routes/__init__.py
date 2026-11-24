from app.routes.public import public_bp
from app.routes.auth import auth_bp
from app.routes.citizen import citizen_bp
from app.routes.admin import admin_bp
from app.routes.officer import officer_bp
from app.routes.worker import worker_bp
from app.routes.api import api_bp

__all__ = [
    'public_bp',
    'auth_bp',
    'citizen_bp',
    'admin_bp',
    'officer_bp',
    'worker_bp',
    'api_bp'
]

import os
from flask import Flask, session, g, render_template
from flask_sqlalchemy import SQLAlchemy
from config import config_by_name, BASE_DIR

db = SQLAlchemy()

def create_app(config_name=None):
    if config_name is None:
        config_name = os.environ.get('FLASK_ENV', 'development')
    
    app = Flask(__name__)
    app.config.from_object(config_by_name.get(config_name, config_by_name['default']))
    
    # Ensure upload directories exist
    upload_dir = app.config['UPLOAD_FOLDER']
    os.makedirs(upload_dir, exist_ok=True)
    os.makedirs(os.path.join(upload_dir, 'complaints'), exist_ok=True)
    os.makedirs(os.path.join(upload_dir, 'proofs'), exist_ok=True)
    
    # Initialize extensions
    db.init_app(app)
    
    # Import models so SQLAlchemy is aware of them
    from app import models

    # Ensure schema migrations for password reset tracking
    with app.app_context():
        try:
            from sqlalchemy import inspect, text
            inspector = inspect(db.engine)
            if 'users' in inspector.get_table_names():
                cols = [c['name'] for c in inspector.get_columns('users')]
                with db.engine.begin() as conn:
                    if 'is_password_reset_required' not in cols:
                        conn.execute(text('ALTER TABLE users ADD COLUMN is_password_reset_required BOOLEAN NOT NULL DEFAULT FALSE'))
                    if 'password_changed_at' not in cols:
                        conn.execute(text('ALTER TABLE users ADD COLUMN password_changed_at DATETIME NULL'))
        except Exception:
            pass
    
    # Context processor for templates
    @app.context_processor
    def inject_global_data():
        from app.utils.translations import get_translation, TRANSLATIONS
        from app.models.user import User
        from app.models.notification import Notification
        
        current_lang = session.get('lang', 'en')
        
        user = None
        user_id = session.get('user_id')
        unread_notifications_count = 0
        if user_id:
            user = User.query.get(user_id)
            if user:
                unread_notifications_count = Notification.query.filter_by(
                    user_id=user.id, is_read=False
                ).count()
        
        def t(key, default=None):
            return get_translation(key, current_lang, default)
            
        return dict(
            current_user=user,
            current_lang=current_lang,
            t=t,
            unread_notifications_count=unread_notifications_count,
            available_languages=[
                {'code': 'en', 'name': 'English', 'native': 'English'},
                {'code': 'ta', 'name': 'Tamil', 'native': 'தமிழ்'},
                {'code': 'hi', 'name': 'Hindi', 'native': 'हिन्दी'}
            ]
        )
    
    # Global error handlers
    @app.errorhandler(403)
    def forbidden(error):
        return render_template('public/error.html', code=403, title="Access Forbidden", message="You do not have permission to access this resource."), 403

    @app.errorhandler(404)
    def not_found(error):
        return render_template('public/error.html', code=404, title="Page Not Found", message="The requested page could not be located."), 404

    @app.errorhandler(500)
    def server_error(error):
        db.session.rollback()
        return render_template('public/error.html', code=500, title="System Error", message="An unexpected error occurred. Our technical team has been notified."), 500

    # Register Blueprints
    from app.routes.public import public_bp
    from app.routes.auth import auth_bp
    from app.routes.citizen import citizen_bp
    from app.routes.admin import admin_bp
    from app.routes.officer import officer_bp
    from app.routes.worker import worker_bp
    from app.routes.api import api_bp
    
    app.register_blueprint(public_bp)
    app.register_blueprint(auth_bp, url_prefix='/auth')
    app.register_blueprint(citizen_bp, url_prefix='/citizen')
    app.register_blueprint(admin_bp, url_prefix='/admin')
    app.register_blueprint(officer_bp, url_prefix='/officer')
    app.register_blueprint(worker_bp, url_prefix='/worker')
    app.register_blueprint(api_bp, url_prefix='/api')
    
    # Static uploads handler for proofs and complaint attachments
    from flask import send_from_directory
    @app.route('/uploads/<path:filename>', strict_slashes=False)
    def uploaded_file(filename):
        clean_filename = filename.replace('\\', '/')
        while clean_filename.startswith('uploads/'):
            clean_filename = clean_filename[8:]
        file_path = os.path.join(app.config['UPLOAD_FOLDER'], clean_filename)
        if not os.path.isfile(file_path):
            alt_path = os.path.join(BASE_DIR, filename.replace('\\', '/'))
            if os.path.isfile(alt_path):
                return send_from_directory(BASE_DIR, filename.replace('\\', '/'))
        return send_from_directory(app.config['UPLOAD_FOLDER'], clean_filename)

    @app.route('/proofs/<path:filename>', strict_slashes=False)
    def uploaded_proofs(filename):
        return send_from_directory(os.path.join(app.config['UPLOAD_FOLDER'], 'proofs'), filename)
    
    return app

# Default application instance for WSGI servers (e.g. gunicorn app:app)
app = create_app()

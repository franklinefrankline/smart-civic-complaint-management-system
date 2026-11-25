import os
import sys
from datetime import timedelta
from urllib.parse import quote_plus, urlparse, parse_qs, urlencode, urlunparse
from dotenv import load_dotenv

# Base directory of the application
BASE_DIR = os.path.abspath(os.path.dirname(__file__))

# Load environment variables from .env file (local development)
load_dotenv(os.path.join(BASE_DIR, '.env'))


def _build_database_config():
    """
    Resolve SQLAlchemy URI and engine options cleanly for local and cloud MySQL.
    Priority:
      1. Explicit DATABASE_URL / MYSQL_URL / SQLALCHEMY_DATABASE_URI
      2. Explicit DB_HOST / MYSQLHOST environment variables (builds MySQL+PyMySQL URI)
      3. Local development default MySQL (127.0.0.1:3306)
      4. Cloud ephemeral SQLite fallback ONLY if no MySQL variables are configured
    """
    is_cloud = bool(
        os.environ.get('RENDER')
        or os.environ.get('VERCEL')
        or os.environ.get('VERCEL_ENV')
        or os.environ.get('AWS_LAMBDA_FUNCTION_NAME')
        or sys.platform.startswith('linux')
    )

    explicit_url = (
        os.environ.get('DATABASE_URL')
        or os.environ.get('MYSQL_URL')
        or os.environ.get('MYSQL_PUBLIC_URL')
        or os.environ.get('MYSQL_DATABASE_URL')
        or os.environ.get('DB_URL')
        or os.environ.get('SQLALCHEMY_DATABASE_URI')
        or ''
    ).strip()

    db_user = (os.environ.get('DB_USER') or os.environ.get('MYSQLUSER') or os.environ.get('MYSQL_USER') or 'root').strip()
    db_password = os.environ.get('DB_PASSWORD') or os.environ.get('MYSQLPASSWORD') or os.environ.get('MYSQL_PASSWORD') or ''
    db_host = (os.environ.get('DB_HOST') or os.environ.get('MYSQLHOST') or os.environ.get('MYSQL_HOST') or '').strip()
    db_port = (os.environ.get('DB_PORT') or os.environ.get('MYSQLPORT') or os.environ.get('MYSQL_PORT') or '3306').strip()
    db_name = (
        os.environ.get('DB_NAME')
        or os.environ.get('DB_DATABASE')
        or os.environ.get('MYSQLDATABASE')
        or os.environ.get('MYSQL_DATABASE')
        or os.environ.get('MYSQL_DB')
        or 'smart_civic_complaints'
    ).strip()

    ssl_required = os.environ.get('DB_SSL', '').lower() in ('1', 'true', 'yes', 'required')
    ssl_ca = os.environ.get('DB_SSL_CA', '').strip()

    if explicit_url:
        if explicit_url.startswith('postgres://'):
            explicit_url = explicit_url.replace('postgres://', 'postgresql://', 1)
        elif explicit_url.startswith('mysql://'):
            explicit_url = explicit_url.replace('mysql://', 'mysql+pymysql://', 1)
        elif explicit_url.startswith('mysql2://'):
            explicit_url = explicit_url.replace('mysql2://', 'mysql+pymysql://', 1)

        # Strip unsupported PyMySQL query args like ssl-mode / sslmode and enable SSL safely
        parsed = urlparse(explicit_url)
        query = parse_qs(parsed.query, keep_blank_values=True)
        for ssl_key in ('ssl-mode', 'ssl_mode', 'sslmode'):
            if ssl_key in query:
                val = (query.pop(ssl_key)[0] or '').lower()
                if val in ('required', 'verify_ca', 'verify_identity', 'true', '1'):
                    ssl_required = True
        if 'mysql' in parsed.scheme and 'charset' not in query:
            query['charset'] = ['utf8mb4']

        clean_query = urlencode(query, doseq=True)
        uri = urlunparse((parsed.scheme, parsed.netloc, parsed.path, parsed.params, clean_query, parsed.fragment))
        db_config_error = None
        if is_cloud and uri.startswith('sqlite') and os.environ.get('ALLOW_EPHEMERAL_SQLITE', '').lower() != 'true':
            db_config_error = (
                "Unsafe SQLite path detected in cloud production. Configure a persistent MySQL "
                "DATABASE_URL in Render Environment Variables so deployment data is preserved."
            )
    elif db_host:
        encoded_user = quote_plus(db_user)
        encoded_pw = quote_plus(db_password)
        auth = f"{encoded_user}:{encoded_pw}" if db_password else encoded_user
        uri = f"mysql+pymysql://{auth}@{db_host}:{db_port}/{db_name}?charset=utf8mb4"
        db_config_error = None
    elif is_cloud and os.environ.get('ALLOW_EPHEMERAL_SQLITE', '').lower() != 'true':
        # Never silently fall back to ephemeral /tmp SQLite in cloud production
        uri = 'sqlite:///:memory:'
        db_config_error = (
            "Production MySQL database is not configured. Set DATABASE_URL (or DB_HOST, DB_USER, "
            "DB_PASSWORD, DB_NAME) in Render Environment Variables. Silent SQLite fallback is disabled."
        )
    elif is_cloud:
        uri = 'sqlite:////tmp/smart_civic.db'
        db_config_error = None
    else:
        encoded_user = quote_plus(db_user)
        encoded_pw = quote_plus(db_password)
        auth = f"{encoded_user}:{encoded_pw}" if db_password else encoded_user
        uri = f"mysql+pymysql://{auth}@127.0.0.1:{db_port}/{db_name}?charset=utf8mb4"
        db_config_error = None

    if 'sqlite' in uri:
        engine_options = {
            'connect_args': {'check_same_thread': False}
        }
    elif 'mysql' in uri:
        connect_args = {
            'connect_timeout': int(os.environ.get('DB_CONNECT_TIMEOUT', 10))
        }
        if ssl_ca:
            connect_args['ssl'] = {'ca': ssl_ca}
        elif ssl_required:
            connect_args['ssl'] = {'ssl_mode': 'PREFERRED'}

        engine_options = {
            'pool_recycle': int(os.environ.get('DB_POOL_RECYCLE', 280)),
            'pool_pre_ping': True,
            'pool_size': int(os.environ.get('DB_POOL_SIZE', 5)),
            'max_overflow': int(os.environ.get('DB_MAX_OVERFLOW', 10)),
            'pool_timeout': 30,
            'connect_args': connect_args
        }
    else:
        engine_options = {
            'pool_recycle': 280,
            'pool_pre_ping': True
        }

    return is_cloud, uri, engine_options, db_user, db_password, db_host or '127.0.0.1', db_port, db_name, db_config_error


_IS_CLOUD, _DB_URI, _ENGINE_OPTS, _DB_USER, _DB_PASSWORD, _DB_HOST, _DB_PORT, _DB_NAME, _DB_CONFIG_ERROR = _build_database_config()


class Config:
    SECRET_KEY = os.environ.get('SECRET_KEY', 'smart-civic-complaint-secret-key-fallback-2026')

    # Database Settings
    DB_USER = _DB_USER
    DB_PASSWORD = _DB_PASSWORD
    DB_HOST = _DB_HOST
    DB_PORT = _DB_PORT
    DB_NAME = _DB_NAME
    IS_CLOUD = _IS_CLOUD
    DB_CONFIG_ERROR = _DB_CONFIG_ERROR

    SQLALCHEMY_DATABASE_URI = _DB_URI
    SQLALCHEMY_TRACK_MODIFICATIONS = False
    SQLALCHEMY_ENGINE_OPTIONS = _ENGINE_OPTS

    # Upload settings: writable /tmp on Cloud/Linux, local directory on Windows
    if IS_CLOUD:
        UPLOAD_FOLDER = os.environ.get('UPLOAD_FOLDER', '/tmp/uploads')
    else:
        UPLOAD_FOLDER = os.environ.get('UPLOAD_FOLDER', os.path.join(BASE_DIR, 'uploads'))
    ALLOWED_EXTENSIONS = {'png', 'jpg', 'jpeg', 'webp', 'pdf'}
    MAX_CONTENT_LENGTH = int(os.environ.get('MAX_CONTENT_LENGTH', 10 * 1024 * 1024))  # 10 MB limit

    # CORS & API Base Configuration
    _extra_origins = [
        o.strip().rstrip('/')
        for o in os.environ.get('CORS_ORIGINS', '').split(',')
        if o.strip()
    ]
    CORS_ALLOWED_ORIGINS = list(dict.fromkeys([
        'https://sccmt.vercel.app',
        'https://smart-civic-complaint-management-sy-indol.vercel.app',
        *_extra_origins,
        *([] if IS_CLOUD else ['http://127.0.0.1:5000', 'http://localhost:5000'])
    ]))
    API_BASE_URL = (
        os.environ.get('API_BASE_URL')
        or os.environ.get('NEXT_PUBLIC_API_BASE_URL')
        or os.environ.get('VITE_API_BASE_URL')
        or ''
    ).strip().rstrip('/')

    # Session & Security
    SESSION_COOKIE_NAME = os.environ.get('SESSION_COOKIE_NAME', 'sccmt_session')
    SESSION_COOKIE_HTTPONLY = True
    SESSION_COOKIE_SAMESITE = os.environ.get('SESSION_COOKIE_SAMESITE', 'Lax')
    SESSION_COOKIE_SECURE = os.environ.get(
        'SESSION_COOKIE_SECURE',
        'true' if IS_CLOUD else 'false'
    ).lower() == 'true'
    SESSION_REFRESH_EACH_REQUEST = False
    PERMANENT_SESSION_LIFETIME = timedelta(
        seconds=int(os.environ.get('PERMANENT_SESSION_LIFETIME', 86400))
    )

    # SLA Response times in hours
    SLA_HOURS = {
        'urgent': 24,    # 1 day
        'high': 48,      # 2 days
        'medium': 96,    # 4 days
        'low': 168       # 7 days
    }

    # Languages supported
    LANGUAGES = ['en', 'ta', 'hi']
    DEFAULT_LANGUAGE = 'en'


class DevelopmentConfig(Config):
    DEBUG = True


class ProductionConfig(Config):
    DEBUG = False
    SEND_FILE_MAX_AGE_DEFAULT = 86400
    SESSION_COOKIE_SECURE = os.environ.get('SESSION_COOKIE_SECURE', 'true').lower() == 'true'


class TestingConfig(Config):
    TESTING = True
    DB_CONFIG_ERROR = None
    SESSION_COOKIE_SECURE = False
    SQLALCHEMY_DATABASE_URI = f"sqlite:///{os.path.join(BASE_DIR, 'test_civic.db')}"
    SQLALCHEMY_ENGINE_OPTIONS = {
        'connect_args': {'check_same_thread': False}
    }


config_by_name = {
    'development': DevelopmentConfig,
    'production': ProductionConfig,
    'testing': TestingConfig,
    'default': ProductionConfig if _IS_CLOUD else DevelopmentConfig
}

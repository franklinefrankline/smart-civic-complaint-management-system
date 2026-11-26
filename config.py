import os
import ssl
import sys
from datetime import timedelta
from urllib.parse import quote_plus, urlparse, parse_qs, urlencode, urlunparse
from dotenv import load_dotenv

# Base directory of the application
BASE_DIR = os.path.abspath(os.path.dirname(__file__))

def _load_secret_env_files():
    """Load Render Secret Files (/etc/secrets/*) without overwriting explicit environment variables."""
    if os.path.isdir('/etc/secrets'):
        for _sec_name in sorted(os.listdir('/etc/secrets')):
            _sec_path = os.path.join('/etc/secrets', _sec_name)
            if os.path.isfile(_sec_path) and ('env' in _sec_name.lower() or _sec_name.startswith('.')):
                load_dotenv(_sec_path, override=False)


# Load local .env once in local dev only; never let local .env pollute cloud runtime
if not os.environ.get('RENDER'):
    load_dotenv(os.path.join(BASE_DIR, '.env'), override=False)
_load_secret_env_files()


def _env_first(env_map, *keys):
    """Case-insensitive and key-whitespace-tolerant lookup across environment variables."""
    for key in keys:
        val = env_map.get(key.upper())
        if val is not None and str(val).strip() != '':
            return str(val)
    return ''


def _build_database_config():
    """
    Resolve SQLAlchemy URI and engine options cleanly for local and cloud MySQL.
    Priority:
      1. Explicit DATABASE_URL / MYSQL_URL / SQLALCHEMY_DATABASE_URI (and aliases)
      2. Explicit DB_HOST / MYSQLHOST / MYSQL_HOST / TIDB_HOST environment variables
      3. Local development default MySQL (127.0.0.1:3306)
      4. Refuse silent /tmp SQLite fallback in cloud production unless explicitly opted in
    """
    _load_secret_env_files()
    norm_env = {k.strip().upper(): v for k, v in os.environ.items()}

    is_cloud = bool(
        norm_env.get('RENDER')
        or norm_env.get('VERCEL')
        or norm_env.get('VERCEL_ENV')
        or norm_env.get('AWS_LAMBDA_FUNCTION_NAME')
        or sys.platform.startswith('linux')
    )

    explicit_url = _env_first(
        norm_env,
        'DATABASE_URL', 'DATABASE_URI', 'DB_URL', 'DB_URI',
        'MYSQL_URL', 'MYSQL_URI', 'MYSQL_PUBLIC_URL', 'MYSQL_DATABASE_URL',
        'TIDB_URL', 'TIDB_DATABASE_URL', 'SQLALCHEMY_DATABASE_URI',
        'DB_CONNECTION_STRING', 'CONNECTION_STRING',
    ).strip().strip('"').strip("'")

    db_host = _env_first(norm_env, 'DB_HOST', 'DATABASE_HOST', 'MYSQLHOST', 'MYSQL_HOST', 'TIDB_HOST', 'HOST_DB').strip().strip('"').strip("'")
    # Support literal HOST / DATABASE / USER / PASSWORD / PORT only when clearly paired for DB use
    bare_host = _env_first(norm_env, 'HOST').strip().strip('"').strip("'")
    if not db_host and bare_host and bare_host not in ('0.0.0.0', '127.0.0.1', 'localhost'):
        if _env_first(norm_env, 'DATABASE', 'DB_NAME', 'MYSQL_DATABASE', 'TIDB_HOST') or 'tidbcloud' in bare_host.lower() or 'mysql' in bare_host.lower():
            db_host = bare_host

    db_user = (_env_first(norm_env, 'DB_USER', 'DB_USERNAME', 'DATABASE_USER', 'DATABASE_USERNAME', 'MYSQLUSER', 'MYSQL_USER', 'MYSQL_USERNAME', 'TIDB_USER', 'TIDB_USERNAME', 'DB_UID', 'USER') or 'root').strip().strip('"').strip("'")
    db_password = _env_first(norm_env, 'DB_PASSWORD', 'DB_PASS', 'DATABASE_PASSWORD', 'DATABASE_PASS', 'MYSQLPASSWORD', 'MYSQL_PASSWORD', 'TIDB_PASSWORD', 'TIDB_PASS', 'PASSWORD')
    db_port = (_env_first(norm_env, 'DB_PORT', 'DATABASE_PORT', 'MYSQLPORT', 'MYSQL_PORT', 'TIDB_PORT') or '3306').strip().strip('"').strip("'")
    if db_port == '3306' and db_host and 'tidbcloud.com' in db_host.lower() and _env_first(norm_env, 'PORT').strip() == '4000':
        db_port = '4000'
    db_name = (
        _env_first(norm_env, 'DB_NAME', 'DB_DATABASE', 'DATABASE_NAME', 'DATABASE_DB', 'MYSQLDATABASE', 'MYSQL_DATABASE', 'MYSQL_DB', 'TIDB_DATABASE', 'TIDB_DB_NAME', 'TIDB_DB', 'DATABASE')
        or 'smart_civic_complaints'
    ).strip().strip('"').strip("'")

    ssl_required = _env_first(norm_env, 'DB_SSL', 'DATABASE_SSL', 'TIDB_SSL', 'MYSQL_SSL').strip().lower() in ('1', 'true', 'yes', 'required')
    ssl_ca_raw = _env_first(norm_env, 'DB_SSL_CA', 'MYSQL_SSL_CA', 'TIDB_SSL_CA', 'SSL_CA').strip().strip('"').strip("'")
    ssl_ca = ssl_ca_raw if (ssl_ca_raw and os.path.isfile(ssl_ca_raw)) else ''

    if explicit_url:
        if explicit_url.startswith('postgres://'):
            explicit_url = explicit_url.replace('postgres://', 'postgresql://', 1)
        elif explicit_url.startswith('mysql://'):
            explicit_url = explicit_url.replace('mysql://', 'mysql+pymysql://', 1)
        elif explicit_url.startswith('mysql2://'):
            explicit_url = explicit_url.replace('mysql2://', 'mysql+pymysql://', 1)

        if explicit_url.startswith('sqlite'):
            uri = explicit_url
        else:
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
        _ignored_keys = {
            'DB_CONNECT_TIMEOUT', 'DB_POOL_RECYCLE', 'DB_POOL_SIZE', 'DB_MAX_OVERFLOW',
            'RENDER_EXTERNAL_URL', 'RENDER_INTERNAL_HOSTNAME', 'HOSTNAME',
        }
        hint_keys = sorted([
            k for k in norm_env.keys()
            if k not in _ignored_keys
            and not k.startswith(('RENDER_GIT_', 'RENDER_SERVICE_', 'RENDER_INSTANCE_', 'VERCEL_'))
            and any(tok in k for tok in ('DB', 'SQL', 'TIDB', 'MYSQL', 'DATABASE', 'HOST', 'URI', 'URL'))
        ])
        keys_note = f" Detected DB-like env keys: {hint_keys}." if hint_keys else " No DB env keys found on Render."
        db_config_error = (
            "Production MySQL database is not configured. Set DATABASE_URL (or DB_HOST, DB_USER, "
            f"DB_PASSWORD, DB_NAME) in Render Environment Variables. Silent SQLite fallback is disabled.{keys_note}"
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
        lower_uri = uri.lower()
        needs_cloud_tls = (
            ssl_required
            or bool(ssl_ca)
            or any(h in lower_uri for h in ('tidbcloud.com', 'aivencloud.com', 'psdb.cloud', 'planetscale', 'sky-sql'))
        )
        if ssl_ca:
            connect_args['ssl'] = {'ca': ssl_ca, 'check_hostname': True, 'verify_mode': True}
        elif needs_cloud_tls:
            resolved_ca = None
            for candidate in (
                '/etc/ssl/certs/ca-certificates.crt',
                '/etc/ssl/cert.pem',
                '/etc/pki/tls/certs/ca-bundle.crt',
            ):
                if os.path.isfile(candidate):
                    resolved_ca = candidate
                    break
            if not resolved_ca:
                try:
                    import certifi
                    resolved_ca = certifi.where()
                except Exception:
                    resolved_ca = None
            if resolved_ca:
                connect_args['ssl'] = {'ca': resolved_ca, 'check_hostname': True, 'verify_mode': True}
            else:
                ctx = ssl.create_default_context()
                if hasattr(ssl, 'VERIFY_X509_STRICT'):
                    ctx.verify_flags &= ~ssl.VERIFY_X509_STRICT
                ctx.check_hostname = True
                ctx.verify_mode = ssl.CERT_REQUIRED
                connect_args['ssl'] = ctx

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

import os
import sys
from datetime import timedelta
from dotenv import load_dotenv

# Base directory of the application
BASE_DIR = os.path.abspath(os.path.dirname(__file__))

# Load environment variables from .env file
load_dotenv(os.path.join(BASE_DIR, '.env'))

class Config:
    SECRET_KEY = os.environ.get('SECRET_KEY', 'smart-civic-complaint-secret-key-fallback-2026')
    
    # Database Settings
    DB_USER = os.environ.get('DB_USER', 'root')
    DB_PASSWORD = os.environ.get('DB_PASSWORD', '')
    DB_HOST = os.environ.get('DB_HOST', '127.0.0.1')
    DB_PORT = os.environ.get('DB_PORT', '3306')
    DB_NAME = os.environ.get('DB_NAME', 'smart_civic_complaints')
    
    # Cloud / Serverless detection
    IS_CLOUD = bool(
        os.environ.get('VERCEL') or 
        os.environ.get('RENDER') or 
        os.environ.get('VERCEL_ENV') or 
        os.environ.get('AWS_LAMBDA_FUNCTION_NAME') or 
        sys.platform.startswith('linux')
    )

    # Priority:
    # 1. Explicit DATABASE_URL (Cloud MySQL, TiDB, PostgreSQL, etc.)
    # 2. If running on Cloud / Linux (Vercel, Render) -> Resilient SQLite in /tmp
    # 3. Local Windows development -> Local XAMPP MySQL
    _explicit_db = os.environ.get('DATABASE_URL')
    if _explicit_db:
        if _explicit_db.startswith('postgres://'):
            _explicit_db = _explicit_db.replace('postgres://', 'postgresql://', 1)
        SQLALCHEMY_DATABASE_URI = _explicit_db
    elif IS_CLOUD:
        SQLALCHEMY_DATABASE_URI = 'sqlite:////tmp/smart_civic.db'
    else:
        SQLALCHEMY_DATABASE_URI = f"mysql+pymysql://{DB_USER}:{DB_PASSWORD}@{DB_HOST}:{DB_PORT}/{DB_NAME}?charset=utf8mb4"

    SQLALCHEMY_TRACK_MODIFICATIONS = False

    # Configure engine options appropriately for dialect
    if 'sqlite' in SQLALCHEMY_DATABASE_URI:
        SQLALCHEMY_ENGINE_OPTIONS = {
            'connect_args': {'check_same_thread': False}
        }
    else:
        SQLALCHEMY_ENGINE_OPTIONS = {
            'pool_recycle': 280,
            'pool_pre_ping': True
        }
    
    # Upload settings: writable /tmp on Cloud/Linux, local directory on Windows
    if IS_CLOUD:
        UPLOAD_FOLDER = '/tmp/uploads'
    else:
        UPLOAD_FOLDER = os.path.join(BASE_DIR, 'uploads')
    ALLOWED_EXTENSIONS = {'png', 'jpg', 'jpeg', 'webp', 'pdf'}
    MAX_CONTENT_LENGTH = 10 * 1024 * 1024  # 10 MB limit
    
    # Session & Security
    SESSION_COOKIE_HTTPONLY = True
    SESSION_COOKIE_SAMESITE = 'Lax'
    SESSION_COOKIE_SECURE = False  # Set to True if running HTTPS in production
    PERMANENT_SESSION_LIFETIME = timedelta(hours=24)
    
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
    SESSION_COOKIE_SECURE = True

class TestingConfig(Config):
    TESTING = True
    SQLALCHEMY_DATABASE_URI = f"sqlite:///{os.path.join(BASE_DIR, 'test_civic.db')}"

config_by_name = {
    'development': DevelopmentConfig,
    'production': ProductionConfig,
    'testing': TestingConfig,
    'default': DevelopmentConfig
}

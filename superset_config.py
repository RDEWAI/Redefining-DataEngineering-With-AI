# Apache Superset Configuration
# For more configuration options, see:
# https://superset.apache.org/docs/installation/configuring-superset

import os
from pathlib import Path

# Superset base directory
BASE_DIR = Path(__file__).parent.resolve()

# Secret key for signing session cookies
# In production, use a proper secret key from environment variables
SECRET_KEY = os.environ.get(
    "SUPERSET_SECRET_KEY", "dev_secret_key_change_in_production"
)

# SQLAlchemy database URI
# Default to SQLite for development
SQLALCHEMY_DATABASE_URI = f"sqlite:///{BASE_DIR}/.superset/superset.db"

# Flask-WTF flag for CSRF
WTF_CSRF_ENABLED = True

# Set to False to allow file uploads
UPLOAD_FOLDER = str(BASE_DIR / ".superset" / "uploads")

# Allow embedding Superset in iframes (for development)
HTTP_HEADERS = {}

# Flask App Builder configuration
FAB_API_SWAGGER_UI = True

# Set the authentication type to database
AUTH_TYPE = 1  # AUTH_DB

# Uncomment to setup Full admin role name
# AUTH_ROLE_ADMIN = 'Admin'

# Uncomment to setup Public role name, no authentication needed
# AUTH_ROLE_PUBLIC = 'Public'

# Will allow user self registration
AUTH_USER_REGISTRATION = True

# The default user self registration role
AUTH_USER_REGISTRATION_ROLE = "Public"

# Feature flags
FEATURE_FLAGS = {
    "DASHBOARD_NATIVE_FILTERS": True,
    "ENABLE_TEMPLATE_PROCESSING": True,
}

# DuckDB data directory (for analytics database)
DUCKDB_DATA_DIR = BASE_DIR / "data" / "duckdb"
DUCKDB_DATABASE = DUCKDB_DATA_DIR / "raw.db"

# Create directories if they don't exist
os.makedirs(BASE_DIR / ".superset", exist_ok=True)
os.makedirs(UPLOAD_FOLDER, exist_ok=True)
os.makedirs(DUCKDB_DATA_DIR, exist_ok=True)

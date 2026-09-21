import os
from datetime import timedelta
from pathlib import Path

from dotenv import load_dotenv

load_dotenv()

BASE_DIR = Path(__file__).resolve().parent.parent

SECRET_KEY = os.getenv("SECRET_KEY", "django-insecure-dev-key")
DEBUG = os.getenv("DEBUG", "True").lower() == "true"
ALLOWED_HOSTS = [h.strip() for h in os.getenv("ALLOWED_HOSTS", "localhost,127.0.0.1").split(",") if h.strip()]

INSTALLED_APPS = [
    "daphne",
    "django.contrib.admin",
    "django.contrib.auth",
    "django.contrib.contenttypes",
    "django.contrib.sessions",
    "django.contrib.messages",
    "django.contrib.staticfiles",
    "django.contrib.postgres",
    "rest_framework",
    "rest_framework_simplejwt",
    "drf_spectacular",
    "corsheaders",
    "channels",
    "accountssu",
    "ticketssu",
    "knowledgesu",
    "chatsu",
    "notificationssu",
    "meapi",
    "globalapi",
]

MIDDLEWARE = [
    "django.middleware.security.SecurityMiddleware",
    "corsheaders.middleware.CorsMiddleware",
    "django.contrib.sessions.middleware.SessionMiddleware",
    "django.middleware.common.CommonMiddleware",
    "django.middleware.csrf.CsrfViewMiddleware",
    "django.contrib.auth.middleware.AuthenticationMiddleware",
    "django.contrib.messages.middleware.MessageMiddleware",
    "django.middleware.clickjacking.XFrameOptionsMiddleware",
]

ROOT_URLCONF = "supportai.urls"
WSGI_APPLICATION = "supportai.wsgi.application"
ASGI_APPLICATION = "supportai.asgi.application"

# Prefer 127.0.0.1 over localhost to avoid IPv6 (::1) connect stalls.
# socket_timeout must be > channels_redis brpop_timeout (5s); Redis 8 defaults to 5s
# which raises TimeoutError on every idle channel receive.
REDIS_URL = os.getenv("REDIS_URL", "redis://127.0.0.1:6380/0")
CHANNEL_LAYERS = {
    "default": {
        "BACKEND": "channels_redis.core.RedisChannelLayer",
        "CONFIG": {
            "hosts": [
                {
                    "address": REDIS_URL,
                    "socket_timeout": 10,
                    "socket_connect_timeout": 5,
                }
            ],
            "capacity": 1500,
            "expiry": 60,
        },
    }
}

TEMPLATES = [
    {
        "BACKEND": "django.template.backends.django.DjangoTemplates",
        "DIRS": [],
        "APP_DIRS": True,
        "OPTIONS": {
            "context_processors": [
                "django.template.context_processors.request",
                "django.contrib.auth.context_processors.auth",
                "django.contrib.messages.context_processors.messages",
            ],
        },
    },
]

_db_engine = os.getenv("DB_ENGINE", "django.db.backends.sqlite3")
if _db_engine == "django.db.backends.sqlite3":
    DATABASES = {
        "default": {
            "ENGINE": "django.db.backends.sqlite3",
            "NAME": BASE_DIR / os.getenv("DB_NAME", "db.sqlite3"),
        }
    }
else:
    DATABASES = {
        "default": {
            "ENGINE": _db_engine,
            "NAME": os.getenv("DB_NAME", "supportai"),
            "USER": os.getenv("DB_USER", "postgres"),
            "PASSWORD": os.getenv("DB_PASSWORD", "postgres"),
            "HOST": os.getenv("DB_HOST", "localhost"),
            "PORT": os.getenv("DB_PORT", "5432"),
        }
    }

AUTH_PASSWORD_VALIDATORS = [
    {"NAME": "django.contrib.auth.password_validation.UserAttributeSimilarityValidator"},
    {"NAME": "django.contrib.auth.password_validation.MinimumLengthValidator"},
    {"NAME": "django.contrib.auth.password_validation.CommonPasswordValidator"},
    {"NAME": "django.contrib.auth.password_validation.NumericPasswordValidator"},
]

AUTH_USER_MODEL = "accountssu.User"

LANGUAGE_CODE = "en-us"
TIME_ZONE = "Asia/Dhaka"
USE_I18N = True
USE_TZ = True

STATIC_URL = "static/"
STATIC_ROOT = BASE_DIR / "staticfiles"
MEDIA_URL = os.getenv("MEDIA_URL", "/media/")
# Prefer writable media_uploads — Docker sometimes left root-owned backend/media/
_media_name = os.getenv("MEDIA_ROOT", "media_uploads").strip() or "media_uploads"
MEDIA_ROOT = BASE_DIR / _media_name
try:
    MEDIA_ROOT.mkdir(parents=True, exist_ok=True)
    if not os.access(MEDIA_ROOT, os.W_OK):
        raise PermissionError(MEDIA_ROOT)
except OSError:
    MEDIA_ROOT = BASE_DIR / "media_uploads"
    MEDIA_ROOT.mkdir(parents=True, exist_ok=True)

DEFAULT_AUTO_FIELD = "django.db.models.BigAutoField"

CORS_ALLOWED_ORIGINS = [
    o.strip()
    for o in os.getenv("CORS_ALLOWED_ORIGINS", "http://localhost:5173").split(",")
    if o.strip()
]
CORS_ALLOW_CREDENTIALS = True

CSRF_TRUSTED_ORIGINS = [
    o.strip()
    for o in os.getenv(
        "CSRF_TRUSTED_ORIGINS",
        "http://localhost:5173,http://127.0.0.1:5173",
    ).split(",")
    if o.strip()
]

REST_FRAMEWORK = {
    "DEFAULT_AUTHENTICATION_CLASSES": (
        "rest_framework_simplejwt.authentication.JWTAuthentication",
    ),
    "DEFAULT_PERMISSION_CLASSES": (
        "rest_framework.permissions.IsAuthenticated",
    ),
    "DEFAULT_PAGINATION_CLASS": "rest_framework.pagination.PageNumberPagination",
    "PAGE_SIZE": 20,
    "DEFAULT_SCHEMA_CLASS": "drf_spectacular.openapi.AutoSchema",
}

SPECTACULAR_SETTINGS = {
    "TITLE": "SupportAI API",
    "DESCRIPTION": "AI Customer Support & Ticket Management System — REST API documentation",
    "VERSION": "1.0.0",
    "SERVE_INCLUDE_SCHEMA": False,
    "COMPONENT_SPLIT_REQUEST": True,
    "SCHEMA_PATH_PREFIX": r"/api/",
    "TAGS": [
        {"name": "Auth", "description": "Register, login, password reset, token refresh"},
        {"name": "Profile", "description": "Current user and agent info"},
        {"name": "Tickets", "description": "Ticket management"},
        {"name": "Chat", "description": "AI chat and sessions"},
        {"name": "Knowledge", "description": "Knowledge base documents (admin)"},
        {"name": "Analytics", "description": "Dashboard and SLA"},
    ],
    "SWAGGER_UI_SETTINGS": {
        "persistAuthorization": True,
        "displayRequestDuration": True,
    },
}

SIMPLE_JWT = {
    "ACCESS_TOKEN_LIFETIME": timedelta(minutes=int(os.getenv("JWT_ACCESS_MINUTES", 60))),
    "REFRESH_TOKEN_LIFETIME": timedelta(days=int(os.getenv("JWT_REFRESH_DAYS", 7))),
    "AUTH_HEADER_TYPES": ("Bearer",),
}

OPENROUTER_API_KEY = os.getenv("OPENROUTER_API_KEY", "")
OPENROUTER_MODEL = os.getenv("OPENROUTER_MODEL", "liquid/lfm-2.5-2.6b:free")

# Vector RAG (pgvector cosine similarity; distance = 1 - similarity)
RAG_TOP_K = int(os.getenv("RAG_TOP_K", "4"))
RAG_MIN_SCORE = float(os.getenv("RAG_MIN_SCORE", "0.32"))
RAG_EMBED_DIM = int(os.getenv("RAG_EMBED_DIM", "384"))

# Google Identity Services (ID token audience). Same value as frontend VITE_GOOGLE_CLIENT_ID.
GOOGLE_CLIENT_ID = os.getenv("GOOGLE_CLIENT_ID", "").strip()

# Frontend base URL used in password-reset emails
FRONTEND_URL = os.getenv("FRONTEND_URL", "http://localhost:5173").rstrip("/")

# Email — set EMAIL_BACKEND=django.core.mail.backends.smtp.EmailBackend for real mail
EMAIL_BACKEND = os.getenv(
    "EMAIL_BACKEND",
    "django.core.mail.backends.console.EmailBackend",
)
EMAIL_HOST = os.getenv("EMAIL_HOST", "smtp.gmail.com")
EMAIL_PORT = int(os.getenv("EMAIL_PORT", "587"))
EMAIL_HOST_USER = os.getenv("EMAIL_HOST_USER", "").strip()
EMAIL_HOST_PASSWORD = os.getenv("EMAIL_HOST_PASSWORD", "").strip()
EMAIL_USE_TLS = os.getenv("EMAIL_USE_TLS", "True").lower() == "true"
EMAIL_USE_SSL = os.getenv("EMAIL_USE_SSL", "False").lower() == "true"
DEFAULT_FROM_EMAIL = os.getenv(
    "DEFAULT_FROM_EMAIL",
    EMAIL_HOST_USER or "SupportAI <noreply@supportai.local>",
).strip()
SERVER_EMAIL = DEFAULT_FROM_EMAIL

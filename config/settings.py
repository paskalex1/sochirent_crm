from pathlib import Path
import environ

BASE_DIR = Path(__file__).resolve().parent.parent

# ────────────────────────────────────────────
# env-переменные (.env в корне проекта)
# ────────────────────────────────────────────
env = environ.Env(
    DEBUG=(bool, False),
)

# читаем .env, если есть
environ.Env.read_env(BASE_DIR / ".env")

# ────────────────────────────────────────────
# БАЗОВЫЕ НАСТРОЙКИ
# ────────────────────────────────────────────
DEBUG = env("DEBUG", default=True)
SECRET_KEY = env("SECRET_KEY", default="dev-secret-change-me")

ALLOWED_HOSTS = env.list(
    "ALLOWED_HOSTS",
    default=["127.0.0.1", "localhost"],
)

CSRF_TRUSTED_ORIGINS = env.list(
    "CSRF_TRUSTED_ORIGINS",
    default=[],
)

# ────────────────────────────────────────────
# ПРИЛОЖЕНИЯ
# ────────────────────────────────────────────
INSTALLED_APPS = [
    "django.contrib.admin",
    "django.contrib.auth",
    "django.contrib.contenttypes",
    "django.contrib.sessions",
    "django.contrib.messages",
    "django.contrib.staticfiles",

    # сторонние
    "rest_framework",
    "django_filters",
    "corsheaders",

    # наши
    "apps.accounts",
    "apps.ai_center",
    "apps.crm",
    "apps.owners",
    "apps.properties",
    "apps.contracts",
    "apps.bookings",
    "apps.operations",
    "apps.finance",
    "apps.staff",
    "apps.reviews",
    "apps.revenue",
]

# ────────────────────────────────────────────
# MIDDLEWARE
# ────────────────────────────────────────────
MIDDLEWARE = [
    "django.middleware.security.SecurityMiddleware",
    "corsheaders.middleware.CorsMiddleware",   # важно: выше CommonMiddleware
    "django.middleware.common.CommonMiddleware",
    "django.contrib.sessions.middleware.SessionMiddleware",
    "django.middleware.csrf.CsrfViewMiddleware",
    "django.contrib.auth.middleware.AuthenticationMiddleware",
    "django.contrib.messages.middleware.MessageMiddleware",
    "django.middleware.clickjacking.XFrameOptionsMiddleware",
]

ROOT_URLCONF = "config.urls"

# ────────────────────────────────────────────
# TEMPLATES
# ────────────────────────────────────────────
TEMPLATES = [
    {
        "BACKEND": "django.template.backends.django.DjangoTemplates",
        "DIRS": [BASE_DIR / "templates"],
        "APP_DIRS": True,
        "OPTIONS": {
            "context_processors": [
                "django.template.context_processors.debug",
                "django.template.context_processors.request",
                "django.contrib.auth.context_processors.auth",
                "django.contrib.messages.context_processors.messages",
            ],
        },
    },
]

WSGI_APPLICATION = "config.wsgi.application"

# ────────────────────────────────────────────
# БАЗА ДАННЫХ
# ────────────────────────────────────────────
# По умолчанию: SQLite (локальная разработка).
# Если в .env задан DB_NAME — используем PostgreSQL.
db_name = env("DB_NAME", default=None)

if db_name:
    DATABASES = {
        "default": {
            "ENGINE": "django.db.backends.postgresql",
            "NAME": db_name,
            "USER": env("DB_USER"),
            "PASSWORD": env("DB_PASSWORD"),
            "HOST": env("DB_HOST", default="127.0.0.1"),
            "PORT": env("DB_PORT", default="5432"),
        }
    }
else:
    DATABASES = {
        "default": {
            "ENGINE": "django.db.backends.sqlite3",
            "NAME": BASE_DIR / "db.sqlite3",
        }
    }

# ────────────────────────────────────────────
# ЛОКАЛИЗАЦИЯ
# ────────────────────────────────────────────
LANGUAGE_CODE = "ru-ru"
TIME_ZONE = "Europe/Moscow"
USE_I18N = True
USE_TZ = True

# ────────────────────────────────────────────
# СТАТИКА / МЕДИА
# ────────────────────────────────────────────
STATIC_URL = "/static/"
STATIC_ROOT = BASE_DIR / "static"

MEDIA_URL = "/media/"
MEDIA_ROOT = BASE_DIR / "media"

DEFAULT_AUTO_FIELD = "django.db.models.BigAutoField"

# ────────────────────────────────────────────
# CORS
# ────────────────────────────────────────────
CORS_ALLOW_ALL_ORIGINS = env.bool("CORS_ALLOW_ALL_ORIGINS", default=True)

# ────────────────────────────────────────────
# DRF / AUTH
# ────────────────────────────────────────────
REST_FRAMEWORK = {
    "DEFAULT_AUTHENTICATION_CLASSES": (
        "rest_framework.authentication.SessionAuthentication",
        "rest_framework.authentication.BasicAuthentication",
    ),
    "DEFAULT_FILTER_BACKENDS": (
        "django_filters.rest_framework.DjangoFilterBackend",
    ),
}

# ────────────────────────────────────────────
# DJANGO AUTH (HTML)
# ────────────────────────────────────────────
LOGIN_URL = "/accounts/login/"
LOGIN_REDIRECT_URL = "/"
LOGOUT_REDIRECT_URL = "/accounts/login/"

# ────────────────────────────────────────────
# ИНТЕГРАЦИОННЫЕ КЛЮЧИ
# ────────────────────────────────────────────
LEAD_API_KEY = env("LEAD_API_KEY", default="")

# ────────────────────────────────────────────
# OpenAI / AI‑сервисы
# ────────────────────────────────────────────
OPENAI_API_KEY = env("OPENAI_API_KEY", default="")
OPENAI_MODEL_NAME = env("OPENAI_MODEL_NAME", default="gpt-5.1")

"""
Django settings for Filial 16 project.
Credenciais e valores sensíveis vêm de variáveis de ambiente (.env em produção).
"""
import os
from pathlib import Path
from datetime import timedelta

from dotenv import load_dotenv

# Carrega .env na raiz do projeto (desenvolvimento e produção)
BASE_DIR = Path(__file__).resolve().parent.parent
load_dotenv(BASE_DIR / '.env')

SECRET_KEY = os.environ.get('DJANGO_SECRET_KEY')

DEBUG = os.environ.get('DJANGO_DEBUG') == '1'

ALLOWED_HOSTS = os.environ.get('ALLOWED_HOSTS', 'localhost,127.0.0.1').split(',')

CSRF_TRUSTED_ORIGINS = [
    x.strip() for x in os.environ.get(
        'CSRF_TRUSTED_ORIGINS',
        'http://localhost:8000,http://127.0.0.1:8000'
    ).split(',') if x.strip()
]

INSTALLED_APPS = [
    'jazzmin',
    'django.contrib.admin',
    'django.contrib.auth',
    'django.contrib.contenttypes',
    'django.contrib.sessions',
    'django.contrib.messages',
    'django.contrib.staticfiles',
    'rest_framework',
    'rest_framework_simplejwt',
    'storages',
    'fila',
    'core',
]

MIDDLEWARE = [
    'django.middleware.security.SecurityMiddleware',
    'django.contrib.sessions.middleware.SessionMiddleware',
    'django.middleware.common.CommonMiddleware',
    'django.middleware.csrf.CsrfViewMiddleware',
    'django.contrib.auth.middleware.AuthenticationMiddleware',
    'django.contrib.messages.middleware.MessageMiddleware',
    'django.middleware.clickjacking.XFrameOptionsMiddleware',
]

ROOT_URLCONF = 'filial16.urls'

TEMPLATES = [
    {
        'BACKEND': 'django.template.backends.django.DjangoTemplates',
        'DIRS': [BASE_DIR / 'templates'],
        'APP_DIRS': True,
        'OPTIONS': {
            'context_processors': [
                'django.template.context_processors.request',
                'django.contrib.auth.context_processors.auth',
                'django.contrib.messages.context_processors.messages',
            ],
        },
    },
]

WSGI_APPLICATION = 'filial16.wsgi.application'

# Desenvolvimento local usa SQLite quando USE_SQLITE=1 (opt-in).
# Sem essa variável, mantém PostgreSQL (comportamento de produção).
if os.environ.get('USE_SQLITE') == '1':
    DATABASES = {
        'default': {
            'ENGINE': 'django.db.backends.sqlite3',
            'NAME': BASE_DIR / 'db.sqlite3',
        }
    }
else:
    DATABASES = {
        'default': {
            'ENGINE': 'django.db.backends.postgresql',
            'NAME': os.environ.get('POSTGRES_DB'),
            'USER': os.environ.get('POSTGRES_USER'),
            'PASSWORD': os.environ.get('POSTGRES_PASSWORD'),
            'HOST': os.environ.get('POSTGRES_HOST'),
            'PORT': os.environ.get('POSTGRES_PORT'),
            'OPTIONS': {},
        }
    }

AUTH_PASSWORD_VALIDATORS = [
    {'NAME': 'django.contrib.auth.password_validation.UserAttributeSimilarityValidator'},
    {'NAME': 'django.contrib.auth.password_validation.MinimumLengthValidator'},
    {'NAME': 'django.contrib.auth.password_validation.CommonPasswordValidator'},
    {'NAME': 'django.contrib.auth.password_validation.NumericPasswordValidator'},
]

LANGUAGE_CODE = 'pt-br'
TIME_ZONE = 'America/Sao_Paulo'
USE_I18N = True
USE_TZ = True

STATIC_URL = 'static/'
STATIC_ROOT = BASE_DIR / 'staticfiles'
STATICFILES_DIRS = [BASE_DIR / 'static']

# MinIO via django-storages + boto3
_MINIO_ENDPOINT = os.environ.get('MINIO_ENDPOINT')
_MINIO_ACCESS = os.environ.get('MINIO_ACCESS_KEY')
_MINIO_SECRET = os.environ.get('MINIO_SECRET_KEY')
_MINIO_BUCKET = os.environ.get('MINIO_BUCKET')
_MINIO_SSL = os.environ.get('MINIO_USE_SSL', '0').lower() in ('1', 'true', 'yes')

AWS_ACCESS_KEY_ID = _MINIO_ACCESS
AWS_SECRET_ACCESS_KEY = _MINIO_SECRET
AWS_STORAGE_BUCKET_NAME = _MINIO_BUCKET
AWS_S3_ENDPOINT_URL = f"{'https' if _MINIO_SSL else 'http'}://{_MINIO_ENDPOINT}"
AWS_S3_USE_SSL = _MINIO_SSL
AWS_DEFAULT_ACL = None
AWS_S3_FILE_OVERWRITE = False       # nunca sobrescrever arquivos existentes silenciosamente
AWS_LOCATION = ''                   # sem prefixo automático
AWS_QUERYSTRING_AUTH = True         # URLs assinadas — arquivos NÃO são públicos
AWS_S3_SIGNATURE_VERSION = 's3v4'  # assinatura moderna (requerida pelo MinIO)
AWS_QUERYSTRING_EXPIRE = 3600      # links expiram em 1 hora

# default = MinIO: todos os uploads de media (fotos, documentos de motorista/cavalo/carreta etc.) vão para o bucket
STORAGES = {
    'default': {
        'BACKEND': 'storages.backends.s3boto3.S3Boto3Storage',
    },
    'staticfiles': {
        'BACKEND': 'django.contrib.staticfiles.storage.StaticFilesStorage',
    },
}

MEDIA_URL = '/media/'

# Upload de PDFs grandes (ex.: processador OST + integração n8n)
# DATA_UPLOAD: corpo inteiro do POST; FILE_UPLOAD: buffer em memória antes de ir ao disco
DATA_UPLOAD_MAX_MEMORY_SIZE = int(os.environ.get('DATA_UPLOAD_MAX_MEMORY_SIZE', 250 * 1024 * 1024))  # 250 MB
FILE_UPLOAD_MAX_MEMORY_SIZE = int(os.environ.get('FILE_UPLOAD_MAX_MEMORY_SIZE', 50 * 1024 * 1024))   # 50 MB (guia n8n)

DEFAULT_AUTO_FIELD = 'django.db.models.BigAutoField'

LOGIN_URL = '/admin/login/'
LOGIN_REDIRECT_URL = '/admin/'
LOGOUT_REDIRECT_URL = '/admin/login/'

# REST Framework: API Key (n8n, X-Api-Key) → JWT (app) → Sessão (navegador)
REST_FRAMEWORK = {
    'DEFAULT_AUTHENTICATION_CLASSES': [
        'rest_framework_simplejwt.authentication.JWTAuthentication',
        'rest_framework.authentication.SessionAuthentication',
    ],
    'DEFAULT_PERMISSION_CLASSES': [
        'rest_framework.permissions.IsAuthenticated',
    ],
}
SIMPLE_JWT = {
    'ACCESS_TOKEN_LIFETIME': timedelta(minutes=60),
    'REFRESH_TOKEN_LIFETIME': timedelta(days=7),
}

LOGGING = {
    'version': 1,
    'disable_existing_loggers': False,
    'handlers': {
        'console': {
            'class': 'logging.StreamHandler',
        },
    },
    'loggers': {

        # Log all 500-level errors with full tracebacks so they appear in docker logs
        'django.request': {
            'handlers': ['console'],
            'level': 'ERROR',
            'propagate': False,
        },
        'django': {
            'handlers': ['console'],
            'level': 'ERROR',
            'propagate': False,
        },
    },
}

# ── Jazzmin ───────────────────────────────────────────────────────────────────
JAZZMIN_SETTINGS = {
    # ── Identidade ────────────────────────────────────────────────────────────
    "site_title":  "Fertran Admin",
    "site_header": "Fertran — Filial 16",
    "site_brand":  "F16",
    "welcome_sign": "Painel de Controle — Filial 16",
    "copyright":    "Fertran Transportes",

    # ── CSS e JS customizados ─────────────────────────────────────────────────
    "custom_css": "admin/css/jazzmin_custom.css",
    "custom_js":  "admin/js/admin_extra.js",

    # ── Tema base (Jazzmin >= 3 / Bootstrap 5) ───────────────────────────────
    # default_theme_mode controla data-bs-theme no <html>.
    # O toggle sol/lua no topbar é injetado pelo admin_extra.js e troca entre
    # 'light' e 'dark' via document.documentElement.setAttribute('data-bs-theme').
    "theme":               "flatly",
    "default_theme_mode":  "light",   # 'light' | 'dark' | 'auto'
    "show_ui_builder":     DEBUG,     # painel de customização só em dev (DEBUG=True)

    # ── Ícones (Font Awesome 5 Free) ──────────────────────────────────────────
    "icons": {
        # Apps
        "core":              "fas fa-truck-moving",
        "fila":              "fas fa-file-alt",
        "auth":              "fas fa-users-cog",
        # core models
        "core.Cavalo":            "fas fa-truck",
        "core.Carreta":           "fas fa-trailer",
        "core.Motorista":         "fas fa-id-card",
        "core.Proprietario":      "fas fa-building",
        "core.Gestor":            "fas fa-user-tie",
        "core.LogCarreta":        "fas fa-history",
        "core.HistoricoGestor":   "fas fa-chart-line",
        "core.CidadeEntrega":     "fas fa-city",
        # fila models
        "fila.OST":               "fas fa-file-invoice",
        "fila.CTe":               "fas fa-file-contract",
        # auth
        "auth.User":              "fas fa-user",
        "auth.Group":             "fas fa-users",
    },
    "default_icon_parents": "fas fa-folder",
    "default_icon_children": "fas fa-circle",

    # ── Links customizados no sidebar (por app) ───────────────────────────────
    "custom_links": {
        "core": [
            {
                "name": "Historico de Frota",
                "url": "admin_frota_historico",
                "icon": "fas fa-route",
            },
        ],
    },

    # ── Ordem do sidebar ──────────────────────────────────────────────────────
    "order_with_respect_to": [
        "core",
        "core.Cavalo", "core.Carreta", "core.Motorista",
        "core.Proprietario", "core.Gestor",
        "core.LogCarreta", "core.HistoricoGestor",
        "core.CidadeEntrega",
        "fila",
        "fila.OST", "fila.CTe",
        "auth",
        "auth.User", "auth.Group",
    ],

    # ── Menu do usuário ───────────────────────────────────────────────────────
    "usermenu_links": [
        {"name": "Meu perfil", "model": "auth.user"},
    ],

    # ── Comportamento ─────────────────────────────────────────────────────────
    "navigation_expanded":   True,
    "related_modal_active":  True,   # FK selectors como modal (mais rápido)
    "show_sidebar":          True,
    "hide_apps":             [],
    "hide_models":           [],

    # ── Formulários ──────────────────────────────────────────────────────────
    # "single_model_with_inlines" | "collapsible" | "horizontal_tabs" | "vertical_tabs"
    "changeform_format": "horizontal_tabs",
}

JAZZMIN_UI_TWEAKS = {
    # Topbar branca + sem borda extra
    "navbar":           "navbar-white navbar-light",
    "no_navbar_border": False,
    "navbar_fixed":     True,

    # Brand: deixa o CSS customizado controlar a cor (#162130)
    "brand_colour":     False,
    "brand_small_text": False,

    # Sidebar navy escuro (cor sobrescrita pelo custom CSS)
    "sidebar":                    "sidebar-dark-primary",
    "sidebar_fixed":              True,
    "sidebar_nav_compact_style":  True,
    "sidebar_nav_flat_style":     False,
    "sidebar_nav_legacy_style":   False,
    "sidebar_nav_child_indent":   True,
    "sidebar_disable_expand":     False,
    "sidebar_nav_small_text":     False,

    # Acento azul (consistente com #3b82f6 do CSS)
    "accent":           "accent-primary",

    # Layout
    "layout_boxed":     False,
    "footer_fixed":     False,
    "body_small_text":  False,
    "footer_small_text": False,

    "button_classes": {
        "primary":   "btn-primary",
        "secondary": "btn-secondary",
        "info":      "btn-info",
        "warning":   "btn-warning",
        "danger":    "btn-danger",
        "success":   "btn-success",
    },
}

# Inoprime FastAPI (wrapper TrackerPrime — mapa de frota)
# Produção: URL interna do container/CT no Proxmox (ex.: http://inoprime-api:8001)
# Dev: http://localhost:8001 (rodar a FastAPI localmente)
INOPRIME_API_URL = os.environ.get('INOPRIME_API_URL', 'http://localhost:8001')

# UAZAPI (WhatsApp API)
UAZAPI_BASE_URL = os.environ.get('UAZAPI_BASE_URL', '')
UAZAPI_WEBHOOK_SECRET = os.environ.get('UAZAPI_WEBHOOK_SECRET', '')

# Google Sheets (Agregamento - Cavalos)
GOOGLE_SHEETS_ENABLED = os.environ.get('GOOGLE_SHEETS_ENABLED', '0').lower() in ('1', 'true', 'yes')
GOOGLE_SHEETS_CREDENTIALS_PATH = os.environ.get('GOOGLE_SHEETS_CREDENTIALS_PATH', '')
GOOGLE_SHEETS_SPREADSHEET_ID = os.environ.get('GOOGLE_SHEETS_SPREADSHEET_ID', '')
GOOGLE_SHEETS_WORKSHEET_NAME = os.environ.get('GOOGLE_SHEETS_WORKSHEET_NAME', 'Cavalos')

# ── Segurança extra em produção (DEBUG=False) ────────────────────────────────
if not DEBUG:
    # Proxy/TLS: Cloudflare já termina o SSL antes do Nginx
    SECURE_PROXY_SSL_HEADER    = ('HTTP_X_FORWARDED_PROTO', 'https')
    SECURE_SSL_REDIRECT        = True

    # Cookies: só trafegam via HTTPS e inacessíveis via JavaScript
    SESSION_COOKIE_SECURE      = True
    SESSION_COOKIE_HTTPONLY    = True
    SESSION_COOKIE_AGE         = 28800   # 8 horas (padrão Django é 2 semanas)
    SESSION_COOKIE_SAMESITE    = 'Lax'
    CSRF_COOKIE_SECURE         = True
    CSRF_COOKIE_HTTPONLY       = True
    CSRF_COOKIE_SAMESITE       = 'Lax'

    # Headers de proteção
    X_FRAME_OPTIONS            = 'DENY'
    SECURE_CONTENT_TYPE_NOSNIFF = True   # impede MIME-sniffing (XSS via upload)
    SECURE_REFERRER_POLICY     = 'strict-origin-when-cross-origin'

    # HSTS: força HTTPS no navegador — aumentar gradualmente após confirmar estabilidade
    # 3600 (1h) → 86400 (1d) → 604800 (1sem) → 31536000 (1ano)
    SECURE_HSTS_SECONDS           = 3600
    SECURE_HSTS_INCLUDE_SUBDOMAINS = True
    SECURE_HSTS_PRELOAD           = False  # habilitar só com valor anual

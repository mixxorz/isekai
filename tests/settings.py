SECRET_KEY = "test-secret-key"

DATABASES = {
    "default": {
        "ENGINE": "django.db.backends.sqlite3",
        "NAME": ":memory:",
    }
}

INSTALLED_APPS = [
    "django.contrib.contenttypes",
    "django.contrib.auth",
    "isekai",
    "tests.testapp",
]

USE_TZ = True

DEFAULT_AUTO_FIELD = "django.db.models.BigAutoField"

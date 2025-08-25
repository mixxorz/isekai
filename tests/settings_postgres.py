import os

from .settings import *  # noqa

DATABASES = {
    "default": {
        "ENGINE": "django.db.backends.postgresql",
        "NAME": os.environ.get("POSTGRES_DB", "isekai_test"),
        "USER": os.environ.get("POSTGRES_USER", "isekai"),
        "PASSWORD": os.environ.get("POSTGRES_PASSWORD", "isekai"),
        "HOST": os.environ.get("POSTGRES_HOST", "localhost"),
        "PORT": os.environ.get("POSTGRES_PORT", "5432"),
    }
}

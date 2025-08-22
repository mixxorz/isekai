import os

import django
import pytest

# Configure Django before importing models
os.environ.setdefault("DJANGO_SETTINGS_MODULE", "tests.settings")
django.setup()


@pytest.fixture(autouse=True)
def _media_tmpdir(settings, tmp_path):
    settings.MEDIA_ROOT = tmp_path

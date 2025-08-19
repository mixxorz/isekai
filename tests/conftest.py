import os

import django
import pytest

# Configure Django before importing models
os.environ.setdefault("DJANGO_SETTINGS_MODULE", "tests.settings")
django.setup()


@pytest.fixture(scope="session")
def django_db_setup(django_db_setup, django_db_blocker):
    """Create tables for our test models."""
    with django_db_blocker.unblock():
        from django.db import connection

        from tests.test_models import ConcreteResource

        with connection.schema_editor() as schema_editor:
            schema_editor.create_model(ConcreteResource)

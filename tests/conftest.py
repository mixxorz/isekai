import os

import django
import pytest

# Configure Django before importing models
os.environ.setdefault("DJANGO_SETTINGS_MODULE", "tests.settings")
django.setup()


@pytest.fixture(autouse=True)
def _media_tmpdir(settings, tmp_path):
    settings.MEDIA_ROOT = tmp_path


@pytest.fixture(autouse=True, scope="session")
def _setup_wagtail_initial_data(django_db_setup, django_db_blocker):
    """Create Wagtail's initial data (root page, site, collection) when migrations are disabled."""
    with django_db_blocker.unblock():
        from django.conf import settings
        from django.contrib.contenttypes.models import ContentType
        from wagtail.models import Page, Site
        from wagtail.models.i18n import Locale
        from wagtail.models.media import Collection

        # Create default locale
        if not Locale.objects.exists():
            Locale.objects.get_or_create(
                language_code=settings.LANGUAGE_CODE,
                defaults={"language_code": "en"},
            )

        # Create root collection if it doesn't exist
        if not Collection.objects.exists():
            Collection.add_root(name="Root")

        # Create root page if it doesn't exist
        if not Page.objects.exists():
            page_content_type = ContentType.objects.get_for_model(Page)
            root_page = Page.add_root(  # type: ignore[attr-defined]
                title="Root",
                slug="root",
                content_type=page_content_type,
            )

            # Create default site
            Site.objects.get_or_create(
                hostname="localhost",
                defaults={
                    "root_page": root_page,
                    "is_default_site": True,
                    "site_name": "Test Site",
                },
            )

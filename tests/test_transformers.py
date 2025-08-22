import pytest
from django.contrib.contenttypes.models import ContentType
from django.core.files.base import ContentFile
from django.utils import timezone
from freezegun import freeze_time

from isekai.operations import transform
from tests.testapp.models import ConcreteResource


@pytest.mark.django_db
class TestTransform:
    def test_transform_saves_specs(self):
        resource = ConcreteResource.objects.create(
            key="url:https://example.com/image.png",
            data_type="blob",
            mime_type="image/png",
            metadata={"alt_text": "A sample image"},
            status=ConcreteResource.Status.MINED,
        )
        resource.blob_data.save("image.png", ContentFile(b"fake image data"))

        now = timezone.now()
        with freeze_time(now):
            transform()

        resource.refresh_from_db()

        assert resource.target_content_type == ContentType.objects.get(
            app_label="wagtailimages", model="image"
        )
        assert resource.target_spec == {
            "title": "image.png",
            "file": "isekai-blob-ref:\\url:https://example.com/image.png",
            "description": "A sample image",
        }

        assert resource.status == ConcreteResource.Status.TRANSFORMED
        assert resource.transformed_at == now

import pytest
from django.contrib.contenttypes.models import ContentType
from django.core.files.base import ContentFile
from django.utils import timezone
from freezegun import freeze_time

from isekai.operations.transform import transform
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

    def test_transform_handles_transformer_chaining(self):
        """Test that transform operation handles transformer chaining correctly."""
        from django.contrib.contenttypes.models import ContentType

        # Create a resource with foo/bar mime type that should be handled by FooBarTransformer
        resource = ConcreteResource.objects.create(
            key="foo:bar-transform-test",
            data_type="text",
            mime_type="foo/bar",
            text_data="some foo bar text",
            metadata={"source": "test"},
            status=ConcreteResource.Status.MINED,
        )

        now = timezone.now()
        with freeze_time(now):
            transform()

        resource.refresh_from_db()

        # Should be transformed by FooBarTransformer
        assert resource.target_content_type == ContentType.objects.get(
            app_label="auth", model="user"
        )
        assert resource.target_spec == {
            "username": "foobar_user",
            "email": "foo@bar.com",
        }

        assert resource.status == ConcreteResource.Status.TRANSFORMED
        assert resource.transformed_at == now

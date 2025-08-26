import pytest
from django.contrib.contenttypes.models import ContentType
from django.core.files.base import ContentFile
from django.utils import timezone
from freezegun import freeze_time

from isekai.pipelines import get_django_pipeline
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
            pipeline = get_django_pipeline()
            pipeline.transform()

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
            pipeline = get_django_pipeline()
            pipeline.transform()

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

    def test_transform_is_idempotent(self):
        """Test that running transform multiple times doesn't re-transform already transformed resources."""
        resource = ConcreteResource.objects.create(
            key="url:https://example.com/test-image.png",
            data_type="blob",
            mime_type="image/png",
            metadata={"alt_text": "Test image"},
            status=ConcreteResource.Status.MINED,
        )
        resource.blob_data.save("test-image.png", ContentFile(b"test image data"))

        # First transform operation
        now = timezone.now()
        with freeze_time(now):
            pipeline = get_django_pipeline()
            pipeline.transform()

        # Verify resource was transformed
        resource.refresh_from_db()
        assert resource.status == ConcreteResource.Status.TRANSFORMED
        assert resource.transformed_at == now
        original_target_spec = resource.target_spec.copy()
        original_content_type_id = resource.target_content_type_id

        # Second transform operation - should not process already transformed resources
        later = now + timezone.timedelta(hours=1)
        with freeze_time(later):
            pipeline = get_django_pipeline()
            pipeline.transform()  # Should be no-op

        # Verify resource state unchanged
        resource.refresh_from_db()
        assert resource.status == ConcreteResource.Status.TRANSFORMED
        assert resource.transformed_at == now  # Timestamp should not change
        assert (
            resource.target_spec == original_target_spec
        )  # Spec should remain the same
        assert (
            resource.target_content_type_id == original_content_type_id
        )  # Content type should remain the same

    def test_no_transformer_found_for_resource(self):
        """Test that resource remains unchanged if no transformer is found."""
        resource = ConcreteResource.objects.create(
            key="url:https://example.com/unknown-file.xyz",
            data_type="blob",
            mime_type="application/xyz",  # Unsupported mime type
            metadata={},
            status=ConcreteResource.Status.MINED,
        )
        resource.blob_data.save("unknown-file.xyz", ContentFile(b"unknown data"))

        now = timezone.now()
        with freeze_time(now):
            pipeline = get_django_pipeline()
            pipeline.transform()

        resource.refresh_from_db()

        # Resource should remain in MINED status with no target spec/content type
        assert resource.status == ConcreteResource.Status.MINED
        assert resource.transformed_at is None
        assert resource.target_spec is None
        assert resource.target_content_type is None
        assert (
            resource.last_error
            == "TransformError: No transformer could handle the resource"
        )

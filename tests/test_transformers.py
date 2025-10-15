import pytest
from django.contrib.contenttypes.models import ContentType
from django.core.files.base import ContentFile
from django.utils import timezone
from freezegun import freeze_time

from isekai.pipelines import Pipeline, get_django_pipeline
from isekai.transformers import BaseTransformer
from isekai.types import BlobRef, Key, ModelRef, ResourceRef, Spec, TextResource
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

        # Verify dependencies are set based on refs in the spec
        dependencies = list(resource.dependencies.all())
        assert len(dependencies) == 1
        assert dependencies[0].key == "url:https://example.com/image.png"
        assert (
            dependencies[0] == resource
        )  # Should reference itself since it's a BlobRef to itself

    def test_transform_handles_transformer_chaining(self):
        """Test that transform operation handles transformer chaining correctly."""

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

    def test_transform_sets_dependencies_from_spec_refs(self):
        """Test that transform operation sets dependencies based on refs in the transformed spec."""
        # Test with FooBarTransformer which doesn't create refs - should have no dependencies
        resource_no_deps = ConcreteResource.objects.create(
            key="foo:test-no-deps",
            data_type="text",
            mime_type="foo/bar",
            text_data="some foo bar text",
            metadata={"source": "test"},
            status=ConcreteResource.Status.MINED,
        )

        pipeline = get_django_pipeline()
        pipeline.transform()

        resource_no_deps.refresh_from_db()

        # FooBarTransformer creates a spec with no refs, so no dependencies
        assert resource_no_deps.status == ConcreteResource.Status.TRANSFORMED
        dependencies = list(resource_no_deps.dependencies.all())
        assert len(dependencies) == 0

    def test_transform_sets_multiple_dependencies_from_spec_refs(self):
        """Test that transform operation correctly sets multiple dependencies from spec refs."""

        # Create dependency resources that will be referenced
        image_resource = ConcreteResource.objects.create(
            key="url:https://example.com/hero-image.jpg",
            status=ConcreteResource.Status.LOADED,
        )

        author_resource = ConcreteResource.objects.create(
            key="gen:author-456",
            status=ConcreteResource.Status.LOADED,
        )

        attachment_resource = ConcreteResource.objects.create(
            key="file:document.pdf",
            status=ConcreteResource.Status.LOADED,
        )

        # Create main resource to transform
        main_resource = ConcreteResource.objects.create(
            key="url:https://example.com/article.html",
            data_type="text",
            mime_type="application/x-test-multi-ref",
            text_data="Test article content",
            metadata={"title": "Test Article"},
            status=ConcreteResource.Status.MINED,
        )

        # Create a custom transformer that produces a spec with multiple refs
        class MultiRefTransformer(BaseTransformer):
            def transform(self, key: Key, resource):
                if resource.mime_type != "application/x-test-multi-ref":
                    return None

                assert isinstance(resource, TextResource)

                return Spec(
                    content_type="testapp.Article",
                    attributes={
                        "title": resource.metadata.get("title", "Default"),
                        "content": resource.text,
                        "hero_image": BlobRef(
                            Key(type="url", value="https://example.com/hero-image.jpg")
                        ),
                        "author": ResourceRef(Key(type="gen", value="author-456")),
                        "category": ModelRef("testapp.Category", pk=1),
                        "attachment": BlobRef(Key(type="file", value="document.pdf")),
                        "metadata": {
                            "related_image": BlobRef(
                                Key(
                                    type="url",
                                    value="https://example.com/hero-image.jpg",
                                )
                            ),  # Duplicate ref
                            "secondary_author": ResourceRef(
                                Key(type="gen", value="author-456")
                            ),  # Duplicate ref
                        },
                        # Non-ref values (should be ignored for dependencies)
                        "published": True,
                        "tags": ["tech", "news"],
                    },
                )

        # Add content type for our test
        ContentType.objects.get_or_create(
            app_label="testapp",
            model="article",
        )

        # Create pipeline with custom transformer
        pipeline = Pipeline(
            seeders=[],
            extractors=[],
            miners=[],
            transformers=[MultiRefTransformer()],
            loaders=[],
        )

        now = timezone.now()
        with freeze_time(now):
            pipeline.transform()

        main_resource.refresh_from_db()

        # Verify resource was transformed
        assert main_resource.status == ConcreteResource.Status.TRANSFORMED
        assert main_resource.transformed_at == now

        # Verify the spec was created correctly with refs
        expected_spec = {
            "title": "Test Article",
            "content": "Test article content",
            "hero_image": "isekai-blob-ref:\\url:https://example.com/hero-image.jpg",
            "author": "isekai-resource-ref:\\gen:author-456",
            "category": "isekai-model-ref:\\testapp.Category?pk=1",
            "attachment": "isekai-blob-ref:\\file:document.pdf",
            "metadata": {
                "related_image": "isekai-blob-ref:\\url:https://example.com/hero-image.jpg",
                "secondary_author": "isekai-resource-ref:\\gen:author-456",
            },
            "published": True,
            "tags": ["tech", "news"],
        }
        assert main_resource.target_spec == expected_spec

        # Verify dependencies are set correctly (unique refs only, no duplicates)
        # Note: ModelRef doesn't create dependencies since it references external DB objects
        dependencies = list(main_resource.dependencies.all())
        dependency_keys = {dep.key for dep in dependencies}

        expected_dependency_keys = {
            "url:https://example.com/hero-image.jpg",  # BlobRef (appears twice but should be unique)
            "gen:author-456",  # ResourceRef (appears twice but should be unique)
            "file:document.pdf",  # BlobRef
        }

        assert len(dependencies) == 3  # Should have exactly 3 unique dependencies
        assert dependency_keys == expected_dependency_keys

        # Verify the actual dependency objects exist
        assert image_resource in dependencies
        assert author_resource in dependencies
        assert attachment_resource in dependencies

    def test_transform_fails_with_invalid_refs(self):
        """Test that transform operation fails when specs reference non-existent resources."""

        # Create main resource to transform
        main_resource = ConcreteResource.objects.create(
            key="url:https://example.com/invalid-refs.html",
            data_type="text",
            mime_type="application/x-test-invalid-refs",
            text_data="Test content with invalid refs",
            metadata={"title": "Invalid Refs Test"},
            status=ConcreteResource.Status.MINED,
        )

        # Create a transformer that produces a spec with refs to non-existent resources
        class InvalidRefTransformer(BaseTransformer):
            def transform(self, key: Key, resource):
                if resource.mime_type != "application/x-test-invalid-refs":
                    return None

                assert isinstance(resource, TextResource)

                return Spec(
                    content_type="testapp.Article",
                    attributes={
                        "title": resource.metadata.get("title", "Default"),
                        "content": resource.text,
                        # Refs to resources that don't exist - this should cause an error
                        "nonexistent_image": BlobRef(
                            Key(type="url", value="https://example.com/missing.jpg")
                        ),
                    },
                )

        # Add content type for our test
        ContentType.objects.get_or_create(
            app_label="testapp",
            model="article",
        )

        # Create pipeline with transformer that references non-existent resources
        pipeline = Pipeline(
            seeders=[],
            extractors=[],
            miners=[],
            transformers=[InvalidRefTransformer()],
            loaders=[],
        )

        # The transform operation should catch the invalid refs and handle them gracefully
        pipeline.transform()

        # Verify that the resource remains in MINED status due to the error
        main_resource.refresh_from_db()
        assert main_resource.status == ConcreteResource.Status.MINED

        # Verify that the error was captured
        assert main_resource.last_error == "TransformError: Invalid refs found in spec"

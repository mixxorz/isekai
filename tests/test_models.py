import pytest
from django.contrib.auth.models import User
from django.contrib.contenttypes.models import ContentType
from django.core.files.base import ContentFile

from isekai.types import BlobResource, TextResource, TransitionError
from tests.testapp.models import Author, ConcreteResource


@pytest.mark.django_db
class TestAbstractResource:
    def test_model_creation(self):
        """Test basic model creation"""
        resource = ConcreteResource.objects.create(key="test-key")
        assert resource.key == "test-key"
        assert resource.seeded_at is not None
        assert resource.status == "seeded"
        assert resource.mime_type == ""
        assert resource.data_type == ""
        assert resource.text_data == ""
        assert resource.last_error == ""

    def test_status_choices(self):
        """Test status choices are available"""
        choices = ConcreteResource.Status.choices
        expected = [
            ("seeded", "Seeded"),
            ("extracted", "Extracted"),
            ("mined", "Mined"),
            ("transformed", "Transformed"),
            ("loaded", "Loaded"),
        ]
        assert choices == expected

    def test_data_property_text(self):
        """Test data property returns text_data when data_type is text"""
        resource = ConcreteResource.objects.create(
            key="test-text", data_type="text", text_data="Hello world"
        )
        assert resource.data == "Hello world"

    def test_data_property_empty(self):
        """Test data property returns None when data_type is empty"""
        resource = ConcreteResource.objects.create(key="test-empty")
        assert resource.data is None

    def test_generic_foreign_key(self):
        """Test generic foreign key setup"""
        user = User.objects.create_user("testuser")
        user_ct = ContentType.objects.get_for_model(User)

        resource = ConcreteResource.objects.create(
            key="test-gfk",
            target_content_type=user_ct,
            target_object_id=user.pk,
        )
        assert resource.target_object == user

    def test_get_resource_object(self):
        text_resource = ConcreteResource.objects.create(
            key="url:https://example.com/text.txt",
            mime_type="text/plain",
            data_type="text",
            text_data="Sample text data",
            metadata={"source": "example.com"},
        )

        resource_obj = text_resource.to_resource_dataclass()

        assert isinstance(resource_obj, TextResource)
        assert resource_obj.mime_type == "text/plain"
        assert resource_obj.text == "Sample text data"
        assert resource_obj.metadata == {"source": "example.com"}

        blob_resource = ConcreteResource.objects.create(
            key="url:https://example.com/blob.bin",
            mime_type="application/octet-stream",
            data_type="blob",
            metadata={"source": "example.com"},
        )
        blob_resource.blob_data.save("blob.bin", ContentFile(b"Sample blob data"))

        resource_obj = blob_resource.to_resource_dataclass()

        assert isinstance(resource_obj, BlobResource)
        assert resource_obj.mime_type == "application/octet-stream"
        with resource_obj.file_ref.open() as f:
            assert f.read() == b"Sample blob data"
        assert resource_obj.filename == "blob.bin"
        assert resource_obj.metadata == {"source": "example.com"}


@pytest.mark.django_db
class TestSeededToExtractedTransition:
    def test_transition_with_text_data(self):
        """Test successful transition from SEEDED to EXTRACTED with text data"""
        resource = ConcreteResource.objects.create(
            key="test-key", text_data="some text", data_type="text"
        )

        resource.transition_to(ConcreteResource.Status.EXTRACTED)

        assert resource.status == ConcreteResource.Status.EXTRACTED
        assert resource.extracted_at is not None
        assert resource.last_error == ""

    def test_transition_with_blob_data(self):
        """Test successful transition from SEEDED to EXTRACTED with blob data"""
        resource = ConcreteResource.objects.create(key="test-key")
        resource.blob_data.save("test.txt", ContentFile(b"blob content"))
        resource.data_type = "blob"
        resource.save()

        resource.transition_to(ConcreteResource.Status.EXTRACTED)

        assert resource.status == ConcreteResource.Status.EXTRACTED
        assert resource.extracted_at is not None
        assert resource.last_error == ""

    def test_transition_without_data_fails(self):
        """Test that transition from SEEDED to EXTRACTED fails without data"""
        resource = ConcreteResource.objects.create(key="test-key")

        with pytest.raises(
            TransitionError, match="Cannot transition to EXTRACTED without data"
        ):
            resource.transition_to(ConcreteResource.Status.EXTRACTED)

        assert resource.status == ConcreteResource.Status.SEEDED
        assert resource.extracted_at is None

    def test_transition_clears_last_error(self):
        """Test that successful transitions clear the last_error field"""
        resource = ConcreteResource.objects.create(
            key="test-key",
            text_data="some text",
            data_type="text",
            last_error="Previous error",
        )

        resource.transition_to(ConcreteResource.Status.EXTRACTED)

        assert resource.status == ConcreteResource.Status.EXTRACTED
        assert resource.last_error == ""


@pytest.mark.django_db
class TestExtractedToMinedTransition:
    def test_transition_from_extracted(self):
        """Test successful transition from EXTRACTED to MINED"""
        resource = ConcreteResource.objects.create(
            key="test-key",
            status=ConcreteResource.Status.EXTRACTED,
            text_data="some text",
            data_type="text",
        )

        resource.transition_to(ConcreteResource.Status.MINED)

        assert resource.status == ConcreteResource.Status.MINED
        assert resource.mined_at is not None
        assert resource.last_error == ""


@pytest.mark.django_db
class TestMinedToTransformedTransition:
    def test_transition_from_mined(self):
        """Test successful transition from MINED to TRANSFORMED"""
        user_ct = ContentType.objects.get_for_model(User)
        resource = ConcreteResource.objects.create(
            key="test-key",
            status=ConcreteResource.Status.MINED,
            text_data="some text",
            data_type="text",
            target_content_type=user_ct,
            target_spec={"name": "Test User", "email": "test@example.com"},
        )

        resource.transition_to(ConcreteResource.Status.TRANSFORMED)

        assert resource.status == ConcreteResource.Status.TRANSFORMED
        assert resource.transformed_at is not None
        assert resource.last_error == ""

    def test_transition_without_target_content_type_fails(self):
        """Test that transition from MINED to TRANSFORMED fails without target content type"""
        resource = ConcreteResource.objects.create(
            key="test-key",
            status=ConcreteResource.Status.MINED,
            text_data="some text",
            data_type="text",
            target_spec={"name": "Test User"},
        )

        with pytest.raises(
            TransitionError,
            match="Cannot transition to TRANSFORMED without target content type and spec",
        ):
            resource.transition_to(ConcreteResource.Status.TRANSFORMED)

        assert resource.status == ConcreteResource.Status.MINED
        assert resource.transformed_at is None

    def test_transition_without_target_spec_fails(self):
        """Test that transition from MINED to TRANSFORMED fails without target spec"""
        user_ct = ContentType.objects.get_for_model(User)
        resource = ConcreteResource.objects.create(
            key="test-key",
            status=ConcreteResource.Status.MINED,
            text_data="some text",
            data_type="text",
            target_content_type=user_ct,
        )

        with pytest.raises(
            TransitionError,
            match="Cannot transition to TRANSFORMED without target content type and spec",
        ):
            resource.transition_to(ConcreteResource.Status.TRANSFORMED)

        assert resource.status == ConcreteResource.Status.MINED
        assert resource.transformed_at is None


@pytest.mark.django_db
class TestTransformedToExtractedTransition:
    def test_transition_from_transformed(self):
        author = Author.objects.create(
            name="Test Author",
            email="test@author.com",
        )

        author_ct = ContentType.objects.get_for_model(Author)
        resource = ConcreteResource.objects.create(
            key="test-key",
            status=ConcreteResource.Status.TRANSFORMED,
            text_data="some text",
            data_type="text",
            target_content_type=author_ct,
            target_object_id=author.pk,
        )

        resource.transition_to(ConcreteResource.Status.LOADED)
        resource.save()

        assert resource.status == ConcreteResource.Status.LOADED
        assert resource.loaded_at is not None

        assert resource.target_object == author

    def test_transition_without_target_object_fails(self):
        article_ct = ContentType.objects.get_by_natural_key("testapp", "article")
        resource = ConcreteResource.objects.create(
            key="test-key",
            status=ConcreteResource.Status.TRANSFORMED,
            text_data="some text",
            data_type="text",
            target_content_type=article_ct,
        )

        with pytest.raises(
            TransitionError,
            match="Cannot transition to LOADED without target object",
        ):
            resource.transition_to(ConcreteResource.Status.LOADED)


@pytest.mark.django_db
class TestInvalidTransitions:
    def test_seeded_to_mined_fails(self):
        """Test that transition from SEEDED to MINED fails"""
        resource = ConcreteResource.objects.create(key="test-key")

        with pytest.raises(
            TransitionError, match="Cannot transition from seeded to mined"
        ):
            resource.transition_to(ConcreteResource.Status.MINED)

        assert resource.status == ConcreteResource.Status.SEEDED

    def test_seeded_to_transformed_fails(self):
        """Test that transition from SEEDED to TRANSFORMED fails"""
        resource = ConcreteResource.objects.create(key="test-key")

        with pytest.raises(
            TransitionError, match="Cannot transition from seeded to transformed"
        ):
            resource.transition_to(ConcreteResource.Status.TRANSFORMED)

        assert resource.status == ConcreteResource.Status.SEEDED

    def test_seeded_to_loaded_fails(self):
        """Test that transition from SEEDED to LOADED fails"""
        resource = ConcreteResource.objects.create(key="test-key")

        with pytest.raises(
            TransitionError, match="Cannot transition from seeded to loaded"
        ):
            resource.transition_to(ConcreteResource.Status.LOADED)

        assert resource.status == ConcreteResource.Status.SEEDED

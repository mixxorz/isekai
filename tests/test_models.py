import pytest
from django.contrib.auth.models import User
from django.contrib.contenttypes.models import ContentType

from isekai.models import AbstractResource


# Create a concrete model for testing
class ConcreteResource(AbstractResource):
    class Meta:
        app_label = "tests"


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
            key="test-gfk", target_content_type=user_ct, target_object_id=user.id
        )
        assert resource.target_object == user

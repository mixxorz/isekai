from isekai.utils.core import get_resource_model
from tests.testapp.models import ConcreteResource


class TestGetResourceModel:
    def test_get_resource_model_returns_concrete_resource(self):
        """Test that get_resource_model returns the concrete resource class."""
        model = get_resource_model()
        assert model is ConcreteResource

from django.apps import apps

from ..models import AbstractResource


def get_resource_model() -> type[AbstractResource]:
    """
    Find the first concrete subclass of AbstractResource.

    Returns:
        Model class: The first concrete subclass of AbstractResource found.

    Raises:
        RuntimeError: If no concrete subclass of AbstractResource is found.
    """

    # Get all registered models
    for model in apps.get_models():
        # Check if the model is a subclass of AbstractResource and not abstract
        if (
            issubclass(model, AbstractResource)
            and model is not AbstractResource
            and not model._meta.abstract
        ):
            return model

    raise RuntimeError(
        "No concrete subclass of AbstractResource found. "
        "Make sure you have created a concrete model that inherits from AbstractResource."
    )

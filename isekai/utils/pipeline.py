from isekai.utils.core import get_resource_model


def get_pipeline_configuration() -> dict[str, list[str]]:
    """
    Extract pipeline configuration from the Resource model.

    Returns:
        Dictionary mapping stage names to lists of processor names.
    """
    Resource = get_resource_model()

    pipeline_config = {}

    # Get seeders
    if hasattr(Resource, "seeders") and Resource.seeders:
        pipeline_config["Seeders"] = [
            seeder.__class__.__name__ for seeder in Resource.seeders
        ]

    # Get extractors
    if hasattr(Resource, "extractors") and Resource.extractors:
        pipeline_config["Extractors"] = [
            extractor.__class__.__name__ for extractor in Resource.extractors
        ]

    # Get miners
    if hasattr(Resource, "miners") and Resource.miners:
        pipeline_config["Miners"] = [
            miner.__class__.__name__ for miner in Resource.miners
        ]

    # Get transformers
    if hasattr(Resource, "transformers") and Resource.transformers:
        pipeline_config["Transformers"] = [
            transformer.__class__.__name__ for transformer in Resource.transformers
        ]

    # Get loaders
    if hasattr(Resource, "loaders") and Resource.loaders:
        pipeline_config["Loaders"] = [
            loader.__class__.__name__ for loader in Resource.loaders
        ]

    return pipeline_config

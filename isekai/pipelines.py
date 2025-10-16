import logging
import random
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from typing import Any, overload

from django.apps import apps
from django.contrib.contenttypes.models import ContentType
from django.core.files.base import ContentFile
from django.db import transaction
from django.db.models import Model, Prefetch

from isekai.types import (
    BlobRef,
    BlobResource,
    FieldFileProxy,
    FileProxy,
    Key,
    MinedResource,
    ModelRef,
    OperationResult,
    PathFileProxy,
    ResourceRef,
    SeededResource,
    Spec,
    TextResource,
    TransformError,
)
from isekai.utils.core import get_resource_model
from isekai.utils.graphs import resolve_build_order

logger = logging.getLogger(__name__)


def get_created_object_stats(objects: list[Any]) -> dict[str, int]:
    """Returns a dictionary with counts of created objects by their model name."""
    stats = {}
    for obj in objects:
        model_name = obj.__class__.__name__
        stats[model_name] = stats.get(model_name, 0) + 1
    return stats


class Pipeline:
    """ETL pipeline that processes resources through seed, extract, mine, transform, load phases."""

    def __init__(
        self,
        seeders: list[Any],
        extractors: list[Any],
        miners: list[Any],
        transformers: list[Any],
        loaders: list[Any],
    ):
        self.seeders = seeders
        self.extractors = extractors
        self.miners = miners
        self.transformers = transformers
        self.loaders = loaders

    def get_configuration(self) -> dict[str, list[str]]:
        """
        Get pipeline configuration.

        Returns:
            Dictionary mapping stage names to lists of processor names.
        """
        pipeline_config = {}

        # Get seeders
        if self.seeders:
            pipeline_config["Seeders"] = [
                seeder.__class__.__name__ for seeder in self.seeders
            ]

        # Get extractors
        if self.extractors:
            pipeline_config["Extractors"] = [
                extractor.__class__.__name__ for extractor in self.extractors
            ]

        # Get miners
        if self.miners:
            pipeline_config["Miners"] = [
                miner.__class__.__name__ for miner in self.miners
            ]

        # Get transformers
        if self.transformers:
            pipeline_config["Transformers"] = [
                transformer.__class__.__name__ for transformer in self.transformers
            ]

        # Get loaders
        if self.loaders:
            pipeline_config["Loaders"] = [
                loader.__class__.__name__ for loader in self.loaders
            ]

        return pipeline_config

    def seed(self) -> OperationResult:
        """Seeds resources from various sources."""
        logger.setLevel(logging.INFO)
        Resource = get_resource_model()

        logger.info(f"Using {len(self.seeders)} seeders")

        failed_seeders = []

        seeded_resources: list[SeededResource] = []
        for seeder in self.seeders:
            try:
                resources = seeder.seed()
            except Exception:
                failed_seeders.append(seeder)
                continue

            seeded_resources.extend(seeder.seed())

        logger.info(f"Found {len(seeded_resources)} resources from seeders")

        resources = []
        for seeded_resource in seeded_resources:
            resource = Resource(
                key=str(seeded_resource.key),
                metadata=seeded_resource.metadata or None,
            )
            resources.append(resource)

            logger.info(f"Seeded resource: {seeded_resource.key}")

        logger.info("Saving seeded resources to database...")

        Resource.objects.bulk_create(resources, ignore_conflicts=True)

        logger.info(f"Seeding completed: {len(resources)} resources processed")

        messages = [
            f"Ran {len(self.seeders)} seeders",
            f"Seeded {len(resources)} resources",
        ]

        if failed_seeders:
            messages.append(f"{len(failed_seeders)} seeders failed")

        return OperationResult(
            result="success" if not failed_seeders else "partial_success",
            messages=messages,
            metadata={},
        )

    def _run_extractors(
        self, key: Key, metadata: dict[str, Any] | None, extractors: list[Any]
    ) -> TextResource | BlobResource | None:
        """Run extractors on a key and return the first successful result.

        This method is designed to run in a thread pool for parallel extraction.
        """
        for extractor in extractors:
            if extracted_resource := extractor.extract(key, metadata):
                return extracted_resource
        return None

    def extract(self) -> OperationResult:
        """Extracts data from a source."""
        logger.setLevel(logging.INFO)
        Resource = get_resource_model()

        logger.info(f"Using {len(self.extractors)} extractors")

        resources = list(Resource.objects.filter(status=Resource.Status.SEEDED))

        logger.info(f"Found {len(resources)} seeded resources to process")

        # Submit extraction tasks to thread pool
        with ThreadPoolExecutor(max_workers=10) as executor:
            # Map futures to resources
            future_to_resource = {}
            for resource in resources:
                logger.info(f"Extracting resource: {resource.key}")
                key = Key.from_string(resource.key)
                future = executor.submit(
                    self._run_extractors, key, resource.metadata, self.extractors
                )
                future_to_resource[future] = resource

            # Process results as they complete
            for future in as_completed(future_to_resource):
                resource = future_to_resource[future]

                try:
                    extracted_resource = future.result()

                    if extracted_resource:
                        resource.mime_type = extracted_resource.mime_type

                        # Merge metadata
                        if resource.metadata is None:
                            resource.metadata = {}

                        resource.metadata.update(dict(extracted_resource.metadata))

                        if isinstance(extracted_resource, TextResource):
                            resource.data_type = "text"
                            resource.text_data = extracted_resource.text

                            logger.info(
                                f"Extracted text data ({extracted_resource.mime_type}) for {resource.key}"
                            )
                        elif isinstance(extracted_resource, BlobResource):
                            resource.data_type = "blob"
                            # Read the temporary file and save it to the model's FileField
                            with extracted_resource.file_ref.open() as temp_file:
                                resource.blob_data.save(
                                    extracted_resource.filename,
                                    ContentFile(temp_file.read()),
                                    save=False,
                                )

                            # Clean up the temporary file
                            assert isinstance(
                                extracted_resource.file_ref, PathFileProxy
                            )
                            extracted_resource.file_ref.path.unlink(missing_ok=True)

                            logger.info(
                                f"Extracted blob data ({extracted_resource.mime_type}) for {resource.key}"
                            )

                    resource.transition_to(Resource.Status.EXTRACTED)
                    resource.save()

                    logger.info(f"Successfully extracted: {resource.key}")

                except Exception as e:
                    resource.last_error = f"{e.__class__.__name__}: {str(e)}"
                    resource.save()

                    logger.error(f"Failed to extract {resource.key}: {e}")

        extracted_count = sum(
            1 for r in resources if r.status == Resource.Status.EXTRACTED
        )
        error_count = sum(1 for r in resources if r.last_error)

        logger.info(
            f"Extraction completed: {extracted_count} successful, {error_count} errors"
        )

        messages = [
            f"Processed {len(resources)} resources",
            f"Extracted {extracted_count} resources",
        ]

        if error_count:
            messages.append(f"Failed to extract {error_count} resources")

        return OperationResult(
            result="success" if error_count == 0 else "partial_success",
            messages=messages,
            metadata={},
        )

    def mine(self) -> OperationResult:
        """Mines extracted resources to discover new resources."""
        logger.setLevel(logging.INFO)
        Resource = get_resource_model()

        logger.info(f"Using {len(self.miners)} miners")

        resources = Resource.objects.filter(status=Resource.Status.EXTRACTED)

        logger.info(f"Found {resources.count()} extracted resources to process")

        seeded_resource_count_before = Resource.objects.filter(
            status=Resource.Status.SEEDED
        ).count()

        for resource in resources:
            logger.info(f"Mining resource: {resource.key}")

            # Create appropriate resource object for mining
            key = Key.from_string(resource.key)
            resource_obj = resource.to_resource_dataclass()

            try:
                # Mine the resource
                mined_resources: list[MinedResource] = []

                for miner in self.miners:
                    mined_resources.extend(miner.mine(key, resource_obj))

                logger.info(
                    f"Discovered {len(mined_resources)} new resources from {resource.key}"
                )

                # Create Resource objects for new keys
                new_resources = [
                    Resource(
                        key=str(mr.key),
                        metadata=dict(mr.metadata) if mr.metadata else None,
                    )
                    for mr in mined_resources
                ]

                # Create resources that don't already exist
                Resource.objects.bulk_create(new_resources, ignore_conflicts=True)

                # Update the original resource that was mined
                resource.transition_to(Resource.Status.MINED)
                resource.save()

                # Clean up temporary file if it was a blob resource
                if isinstance(resource_obj, BlobResource) and isinstance(
                    resource_obj.file_ref, PathFileProxy
                ):
                    resource_obj.file_ref.path.unlink(missing_ok=True)

                logger.info(f"Successfully mined: {resource.key}")

            except Exception as e:
                resource.last_error = f"{e.__class__.__name__}: {str(e)}"
                resource.save()

                logger.error(f"Failed to mine {resource.key}: {e}")

        seeded_resource_count_after = Resource.objects.filter(
            status=Resource.Status.SEEDED
        ).count()

        newly_seeded_count = seeded_resource_count_after - seeded_resource_count_before
        mined_count = sum(1 for r in resources if r.status == Resource.Status.MINED)
        error_count = sum(1 for r in resources if r.last_error)

        logger.info(f"Mining completed: {mined_count} successful, {error_count} errors")

        messages = [
            f"Processed {len(resources)} resources",
            f"Mined {mined_count} resources",
        ]

        if error_count:
            messages.append(f"Failed to mine {error_count} resources")

        messages.append(f"Seeded {newly_seeded_count} new resources")

        return OperationResult(
            result="success" if not error_count else "partial_success",
            messages=messages,
            metadata={
                "newly_seeded_count": newly_seeded_count,
            },
        )

    def transform(self) -> OperationResult:
        """Transforms mined resources into target specifications."""
        logger.setLevel(logging.INFO)
        Resource = get_resource_model()

        logger.info(f"Using {len(self.transformers)} transformers")

        content_types = ContentType.objects.values_list("app_label", "model", "pk")

        ct_map = {f"{app_label}.{model}": pk for app_label, model, pk in content_types}

        resources = Resource.objects.filter(status=Resource.Status.MINED)

        logger.info(f"Found {resources.count()} mined resources to process")

        for resource in resources:
            logger.info(f"Transforming resource: {resource.key}")

            try:
                key = Key.from_string(resource.key)
                resource_obj = resource.to_resource_dataclass()

                # Use the first transformer that can handle the resource
                spec = None
                for transformer in self.transformers:
                    if spec := transformer.transform(key, resource_obj):
                        break

                if spec:
                    try:
                        content_type = ct_map[spec.content_type.lower()]
                    except KeyError as e:
                        raise TransformError(
                            f"Unknown content type: {spec.content_type}"
                        ) from e

                    spec_dict = spec.to_dict()
                    resource.target_content_type_id = content_type
                    resource.target_spec = spec_dict["attributes"]

                    # Set dependencies based on refs found in the spec
                    refs = spec.find_refs()
                    dependency_key_strings = [str(ref.key) for ref in refs]

                    # Check if all referenced resources exist
                    if dependency_key_strings:
                        existing_keys = set(
                            Resource.objects.filter(
                                key__in=dependency_key_strings
                            ).values_list("key", flat=True)
                        )
                        missing_keys = set(dependency_key_strings) - existing_keys
                        if missing_keys:
                            raise TransformError("Invalid refs found in spec")

                    resource.transition_to(Resource.Status.TRANSFORMED)

                    with transaction.atomic():
                        resource.save()
                        resource.dependencies.set(dependency_key_strings)  # type: ignore[call-arg]

                    logger.info(f"Successfully transformed: {resource.key}")
                else:
                    raise TransformError("No transformer could handle the resource")

            except Exception as e:
                resource.last_error = f"{e.__class__.__name__}: {str(e)}"
                resource.save()

                logger.error(f"Failed to transform {resource.key}: {e}")

        transformed_count = sum(
            1 for r in resources if r.status == Resource.Status.TRANSFORMED
        )
        error_count = sum(1 for r in resources if r.last_error)

        logger.info(
            f"Transform completed: {transformed_count} successful, {error_count} errors"
        )

        messages = [
            f"Processed {len(resources)} resources",
            f"Transformed {transformed_count} resources",
        ]

        if error_count:
            messages.append(f"Failed to transform {error_count} resources")

        return OperationResult(
            result="success" if error_count == 0 else "partial_success",
            messages=messages,
            metadata={},
        )

    def load(self) -> OperationResult:
        """Loads objects from resources"""
        logger.setLevel(logging.INFO)
        Resource = get_resource_model()

        logger.info(f"Using {len(self.loaders)} loaders")

        resources = Resource.objects.filter(
            status=Resource.Status.TRANSFORMED,
        ).prefetch_related(
            Prefetch(
                "dependencies",
                queryset=Resource.objects.only("key", "status"),
            )
        )

        logger.info(f"Found {resources.count()} transformed resources to process")

        # Calculate build order
        key_to_resource = {resource.key: resource for resource in resources}
        key_to_dependencies = {
            resource.key: list(resource.dependencies.all()) for resource in resources
        }
        nodes = key_to_resource.keys()
        edges = [
            (resource.key, dep.key)
            for resource in resources
            for dep in resource.dependencies.all()
            # When calculating the build order, we only need to deal with resources
            # that have not been loaded yet. Dependency resources that are already
            # loaded do not need to be taken into consideration, because we can
            # resolve to them immediately; no need for two-phase loading
            if dep.key in nodes
        ]

        graph = resolve_build_order(nodes, edges)

        # Track resources that can't be loaded due to unready dependencies.
        # Since graph is in topological order (dependencies first), cascading happens
        # automatically. when a dependency is marked unready, dependents will see it
        # in this set when processed later and also become unready. The topological
        # sort guarantees dependents are never processed before their dependencies.
        unready_resources = set()

        ready_states = (Resource.Status.LOADED, Resource.Status.TRANSFORMED)

        for node in graph:
            for resource_key in node:
                dependencies = key_to_dependencies[resource_key]
                if any(
                    dep.status not in ready_states or dep.key in unready_resources
                    for dep in dependencies
                ):
                    # If any of the resources in this node becomes unready, the
                    # whole node is unready
                    unready_resources.update(node)
                    break

        logger.info(f"Build order resolved into {len(graph)} phases")

        # Load the objects
        key_to_obj: dict[str, Model] = {}

        @overload
        def resolver(ref: BlobRef) -> FileProxy: ...
        @overload
        def resolver(ref: ResourceRef) -> Model | int | str: ...
        @overload
        def resolver(ref: ModelRef) -> Model: ...

        def resolver(
            ref: BlobRef | ResourceRef | ModelRef,
        ) -> FileProxy | Model | int | str:
            # If it's a BlobRef, we must return a FileProxy
            if type(ref) is BlobRef:
                if str(ref.key) in key_to_obj:
                    resource = key_to_resource[str(ref.key)]
                    if resource.blob_data:
                        return FieldFileProxy(ff=resource.blob_data)

                # If it's not there, then it's a reference to a resource that has
                # already been loaded
                if obj := Resource.objects.filter(key=str(ref.key)).first():
                    if obj and obj.blob_data:
                        return FieldFileProxy(ff=obj.blob_data)

            # If it's a ResourceRef, resolve to model instance or attribute
            elif type(ref) is ResourceRef:
                # Try to find the object in the pool of resources currently being loaded
                if str(ref.key) in key_to_obj:
                    obj = key_to_obj[str(ref.key)]
                    # Traverse attribute path
                    for attr in ref.ref_attr_path:
                        obj = getattr(obj, attr)
                    return obj

                # If it's not there, then it's a reference to a resource that has
                # already been loaded
                if resource := Resource.objects.filter(key=str(ref.key)).first():
                    # PK optimization: return target_object_id directly if attr_path is ("pk",)
                    if ref.ref_attr_path == ("pk",) and resource.target_object_id:
                        return resource.target_object_id
                    # Otherwise fetch target_object and traverse
                    if obj := resource.target_object:
                        for attr in ref.ref_attr_path:
                            obj = getattr(obj, attr)
                        return obj

            # If it's a ModelRef, fetch from DB using content_type and lookup_kwargs
            elif type(ref) is ModelRef:
                app_label, model_name = ref.ref_content_type.split(".", 1)
                model_class = apps.get_model(app_label, model_name)
                obj = model_class.objects.get(**ref.ref_lookup_kwargs)
                # Traverse attribute path
                for attr in ref.ref_attr_path:
                    obj = getattr(obj, attr)
                return obj

            # If the framework is working correctly, it is logically impossible to
            # reach this case. The build order resolver ensures that all dependency
            # resources are created either before it's needed, or at the same time
            # as the resource that references it.
            raise ValueError(f"Unable to resolve reference: {ref}")

        for node in graph:
            # Each node in the graph is comprised of one OR MORE resources.

            # If any resource in this node is unready, skip the entire node
            if any(rkey in unready_resources for rkey in node):
                logger.warning(f"Skipping node with unready dependencies: {list(node)}")
                continue

            # If there is more than one resource, that means that those resources
            # need to be loaded together using a two-phase loading process in order
            # to resolve circular dependencies.
            # Single resources are also loaded, but they don't need the same
            # circular dependency handling.
            if len(node) == 1:
                logger.info(f"Loading resource: {list(node)[0]}")
            else:
                logger.info(
                    f"Loading {len(node)} resources with circular dependencies: {list(node)}"
                )

            specs = []
            for resource_key in node:
                resource = key_to_resource[resource_key]
                ct = resource.target_content_type
                assert ct, "Resource must have a target content type to be loaded"
                model_class = ct.model_class()
                assert model_class, "Unable to resolve model class for content type"

                key = Key.from_string(resource.key)
                spec = Spec.from_dict(
                    {
                        "content_type": f"{model_class._meta.label}",
                        "attributes": resource.target_spec,
                    }
                )
                specs.append((key, spec))

            # Load the objects
            try:
                with transaction.atomic():
                    resources_to_update = []
                    created_objects = []
                    for loader in self.loaders:
                        if created_objects := loader.load(specs, resolver):
                            break

                    for ckey, cobject in created_objects:
                        key_to_obj[str(ckey)] = cobject
                        resource = key_to_resource[str(ckey)]
                        resource.target_object_id = cobject.pk
                        resource.transition_to(Resource.Status.LOADED)
                        resources_to_update.append(resource)

                        logger.info(f"Successfully loaded: {resource.key}")

                    Resource.objects.bulk_update(
                        resources_to_update,
                        [
                            "target_object_id",
                            "status",
                            "loaded_at",
                            "last_error",
                        ],
                    )
            except Exception as e:
                # Mark resources in this node as failed
                failed_resources = []
                for resource_key in node:
                    resource = key_to_resource[resource_key]
                    resource.refresh_from_db()
                    resource.last_error = f"{e.__class__.__name__}: {str(e)}"
                    failed_resources.append(resource)

                    logger.error(f"Failed to load {resource.key}: {e}")

                # Save the failed resources
                Resource.objects.bulk_update(
                    failed_resources,
                    ["last_error"],
                )

                # Stop processing - dependent nodes will also fail
                logger.error(
                    "Stopping load process due to node failure - remaining nodes would likely fail due to missing dependencies"
                )

                return OperationResult(
                    result="failure",
                    messages=[
                        f"Load failed at node with resources: {list(node)}",
                        f"Error: {e.__class__.__name__}: {str(e)}",
                    ],
                    metadata={
                        "object_stats": get_created_object_stats(
                            list(key_to_obj.values())
                        )
                    },
                )

        all_resources = list(key_to_resource.values())
        loaded_count = sum(
            1 for r in all_resources if r.status == Resource.Status.LOADED
        )
        skipped_count = sum(1 for r in all_resources if r.key in unready_resources)

        logger.info(
            f"Load completed: {loaded_count} successful, {skipped_count} skipped"
        )

        messages = [
            f"Processed {len(all_resources)} resources",
            f"Loaded {loaded_count} resources",
        ]

        if skipped_count > 0:
            messages.append(
                f"Skipped {skipped_count} resources due to unready dependencies"
            )

        return OperationResult(
            result="success",
            messages=messages,
            metadata={
                "object_stats": get_created_object_stats(list(key_to_obj.values()))
            },
        )


class DummyPipeline(Pipeline):
    """A dummy pipeline that simulates operations without actually doing any work."""

    def __init__(self, simulate_errors: bool = False, simulate_warnings: bool = False):
        # Create dummy processors
        dummy_processors = [
            type("DummyProcessor", (), {"__name__": f"Processor{i}"})()
            for i in range(2)
        ]

        super().__init__(
            seeders=dummy_processors,
            extractors=dummy_processors,
            miners=dummy_processors,
            transformers=dummy_processors,
            loaders=dummy_processors,
        )
        self.simulate_errors = simulate_errors
        self.simulate_warnings = simulate_warnings

    def get_configuration(self) -> dict[str, list[str]]:
        """Return dummy configuration."""
        return {
            "Seeders": ["DummySeeder", "AnotherDummySeeder"],
            "Extractors": ["DummyExtractor", "FakeExtractor"],
            "Miners": ["DummyMiner"],
            "Transformers": ["DummyTransformer", "FakeTransformer"],
            "Loaders": ["DummyLoader"],
        }

    def _simulate_work(
        self, operation_name: str, count: int | None = None
    ) -> tuple[int, int, int]:
        """Simulate work and return (processed, successful, errors)."""
        if count is None:
            count = random.randint(5, 20)

        # Simulate some time passing
        time.sleep(random.uniform(0.1, 0.5))

        # Map operation names to attribute names
        attr_map = {
            "seed": "seeders",
            "extract": "extractors",
            "mine": "miners",
            "transform": "transformers",
            "load": "loaders",
        }
        attr_name = attr_map.get(operation_name.lower(), operation_name.lower() + "s")
        processors = getattr(self, attr_name, [])
        logger.info(f"Using {len(processors)} {operation_name.lower()}s")
        logger.info(f"Found {count} resources to process")

        # Simulate processing each resource
        successful = 0
        errors = 0

        for i in range(count):
            # Simulate some processing time
            time.sleep(random.uniform(0.01, 0.05))

            # Simulate success/failure based on flags
            if self.simulate_errors and random.random() < 0.2:  # 20% error rate
                logger.error(f"Failed to process resource {i}: Simulated error")
                errors += 1
            else:
                logger.info(f"Successfully processed resource {i}")
                successful += 1

        logger.info("Saving changes to database...")
        logger.info(
            f"{operation_name} completed: {successful} successful, {errors} errors"
        )

        return count, successful, errors

    def seed(self) -> OperationResult:
        """Simulate seeding operation."""
        logger.setLevel(logging.INFO)

        _processed, successful, errors = self._simulate_work("Seed")

        messages = [
            f"Ran {len(self.seeders)} seeders",
            f"Seeded {successful} resources",
        ]

        if errors:
            messages.append(f"{errors} seeders failed")

        if self.simulate_errors and errors > 0:
            result = "partial_success"
        else:
            result = "success"

        return OperationResult(
            result=result,
            messages=messages,
            metadata={"seeded_count": successful},
        )

    def extract(self) -> OperationResult:
        """Simulate extraction operation."""
        logger.setLevel(logging.INFO)

        processed, successful, errors = self._simulate_work("Extract")

        messages = [
            f"Processed {processed} resources",
            f"Extracted {successful} resources",
        ]

        if errors:
            messages.append(f"Failed to extract {errors} resources")

        result = "success" if errors == 0 else "partial_success"

        return OperationResult(
            result=result,
            messages=messages,
            metadata={},
        )

    def mine(self) -> OperationResult:
        """Simulate mining operation."""
        logger.setLevel(logging.INFO)

        processed, successful, errors = self._simulate_work("Mine")
        # 50% chance of seeding 0 new resources to prevent infinite loop
        newly_seeded = 0 if random.random() < 0.5 else random.randint(2, 8)

        messages = [
            f"Processed {processed} resources",
            f"Mined {successful} resources",
        ]

        if errors:
            messages.append(f"Failed to mine {errors} resources")

        messages.append(f"Seeded {newly_seeded} new resources")

        result = "success" if errors == 0 else "partial_success"

        return OperationResult(
            result=result,
            messages=messages,
            metadata={"newly_seeded_count": newly_seeded},
        )

    def transform(self) -> OperationResult:
        """Simulate transformation operation."""
        logger.setLevel(logging.INFO)

        processed, successful, errors = self._simulate_work("Transform")

        messages = [
            f"Processed {processed} resources",
            f"Transformed {successful} resources",
        ]

        if errors:
            messages.append(f"Failed to transform {errors} resources")

        result = "success" if errors == 0 else "partial_success"

        return OperationResult(
            result=result,
            messages=messages,
            metadata={},
        )

    def load(self) -> OperationResult:
        """Simulate loading operation."""
        logger.setLevel(logging.INFO)

        processed, successful, _errors = self._simulate_work("Load")

        # Simulate object creation stats
        object_stats = {
            "Article": random.randint(3, 8),
            "Image": random.randint(1, 5),
            "Author": random.randint(1, 3),
        }

        logger.info(f"Build order resolved into {random.randint(1, 3)} phases")

        for i in range(processed):
            if i < successful:
                logger.info(f"Loading resource: dummy_resource_{i}")
                logger.info(f"Successfully loaded: dummy_resource_{i}")

        messages = [
            f"Processed {processed} resources",
            f"Loaded {successful} resources",
        ]

        if self.simulate_errors and random.random() < 0.1:  # 10% chance of failure
            return OperationResult(
                result="failure",
                messages=[
                    "Load failed at node with resources: ['dummy_resource_1']",
                    "Error: SimulatedError: Database connection failed",
                ],
                metadata={"object_stats": object_stats},
            )

        result = "success"

        return OperationResult(
            result=result,
            messages=messages,
            metadata={"object_stats": object_stats},
        )


def get_dummy_pipeline(
    simulate_errors: bool = False, simulate_warnings: bool = False
) -> DummyPipeline:
    """Returns a DummyPipeline instance for testing."""
    return DummyPipeline(
        simulate_errors=simulate_errors, simulate_warnings=simulate_warnings
    )


def get_django_pipeline() -> Pipeline:
    """Returns a Pipeline instance configured using the Django Resource model"""
    Resource = get_resource_model()

    return Pipeline(
        seeders=Resource.seeders,
        extractors=Resource.extractors,
        miners=Resource.miners,
        transformers=Resource.transformers,
        loaders=Resource.loaders,
    )

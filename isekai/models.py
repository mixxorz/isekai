from typing import TYPE_CHECKING, Any, Literal

from django.contrib.contenttypes.fields import GenericForeignKey
from django.contrib.contenttypes.models import ContentType
from django.db import models
from django.utils import timezone

from isekai.extractors import BaseExtractor
from isekai.loaders import BaseLoader
from isekai.miners import BaseMiner
from isekai.seeders import BaseSeeder
from isekai.transformers import BaseTransformer
from isekai.types import BlobResource, FieldFileProxy, TextResource, TransitionError


class AbstractResource(models.Model):
    class Status(models.TextChoices):
        SEEDED = "seeded", "Seeded"
        EXTRACTED = "extracted", "Extracted"
        MINED = "mined", "Mined"
        TRANSFORMED = "transformed", "Transformed"
        LOADED = "loaded", "Loaded"

    key = models.CharField(max_length=255, primary_key=True, db_index=True)

    # Data
    mime_type = models.CharField(max_length=100, blank=True)
    data_type: Literal["text", "blob"] = models.CharField(  # type: ignore[assignment]
        max_length=10,
        choices=[("text", "Text"), ("blob", "Blob")],
        blank=True,
    )
    blob_data = models.FileField(upload_to="resource_blobs/", blank=True, null=True)
    text_data = models.TextField(
        blank=True,
    )
    metadata: dict[str, Any] = models.JSONField(blank=True, null=True)  # type: ignore[assignment]

    # Resources this resource depends on
    dependencies = models.ManyToManyField(
        "self",
        symmetrical=False,
        related_name="dependent_resources",
        blank=True,
    )

    # Target
    target_content_type = models.ForeignKey(
        ContentType, on_delete=models.CASCADE, blank=True, null=True
    )
    target_spec: dict[str, Any] = models.JSONField(blank=True, null=True)  # type: ignore[assignment]
    target_object_id = models.CharField(max_length=36, blank=True, default="")
    target_object = GenericForeignKey("target_content_type", "target_object_id")

    # Audit fields
    status = models.CharField(
        max_length=20,
        choices=Status.choices,
        default=Status.SEEDED,
    )
    seeded_at = models.DateTimeField(auto_now_add=True, null=True)
    extracted_at = models.DateTimeField(blank=True, null=True)
    mined_at = models.DateTimeField(blank=True, null=True)
    transformed_at = models.DateTimeField(blank=True, null=True)
    loaded_at = models.DateTimeField(blank=True, null=True)

    # Error tracking
    last_error = models.TextField(blank=True)

    # Processors
    seeders: list[BaseSeeder] = []
    extractors: list[BaseExtractor] = []
    miners: list[BaseMiner] = []
    transformers: list[BaseTransformer] = []
    loaders: list[BaseLoader] = []

    # Types
    if TYPE_CHECKING:
        dependencies: models.ManyToManyField["AbstractResource", Any]
        target_content_type_id: int | None

    class Meta:
        abstract = True

    @property
    def data(self):
        if self.data_type == "text":
            return self.text_data
        elif self.data_type == "blob":
            return self.blob_data
        return None

    def transition_to(self, next_status: Status):
        """Transition the resource to a new status.

        1. Ensures that only valid transitions are allowed.
        2. Ensures that the resource is valid for the next status.
        3. Updates the status and relevant timestamps.
        """

        # SEEDED -> EXTRACTED
        if self.status == self.Status.SEEDED and next_status == self.Status.EXTRACTED:
            if not self.text_data and not self.blob_data:
                raise TransitionError("Cannot transition to EXTRACTED without data")

            self.last_error = ""
            self.status = next_status
            self.extracted_at = timezone.now()
        # EXTRACTED -> MINED
        elif self.status == self.Status.EXTRACTED and next_status == self.Status.MINED:
            self.last_error = ""
            self.status = next_status
            self.mined_at = timezone.now()
        # MINED -> TRANSFORMED
        elif (
            self.status == self.Status.MINED and next_status == self.Status.TRANSFORMED
        ):
            if not self.target_content_type_id or not self.target_spec:
                raise TransitionError(
                    "Cannot transition to TRANSFORMED without target content type and spec"
                )

            self.last_error = ""
            self.status = next_status
            self.transformed_at = timezone.now()
        # TRANSFORMED -> LOADED
        elif (
            self.status == self.Status.TRANSFORMED and next_status == self.Status.LOADED
        ):
            if not self.target_object_id:
                raise TransitionError(
                    "Cannot transition to LOADED without target object"
                )

            self.last_error = ""
            self.status = next_status
            self.loaded_at = timezone.now()
        else:
            raise TransitionError(
                f"Cannot transition from {self.status} to {next_status}"
            )

    def to_resource_dataclass(self) -> TextResource | BlobResource:
        """Returns a TextResource or BlobResource for this Resource"""

        if self.data_type == "text":
            resource_obj = TextResource(
                mime_type=self.mime_type,
                text=self.text_data,
                metadata=self.metadata or {},
            )
        else:
            file_ref = FieldFileProxy(ff=self.blob_data)
            resource_obj = BlobResource(
                mime_type=self.mime_type,
                filename=file_ref.name,
                file_ref=file_ref,
                metadata=self.metadata or {},
            )

        return resource_obj

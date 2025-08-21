from typing import Literal

from django.contrib.contenttypes.fields import GenericForeignKey
from django.contrib.contenttypes.models import ContentType
from django.db import models
from django.utils import timezone

from isekai.extractors import BaseExtractor
from isekai.miners import BaseMiner
from isekai.seeders import BaseSeeder
from isekai.types import TransitionError


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
    metadata = models.JSONField(blank=True, null=True)

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
    target_object_id = models.PositiveIntegerField(blank=True, null=True)
    target_object = GenericForeignKey("target_content_type", "target_object_id")
    target_spec = models.JSONField(blank=True, null=True)

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
    seeder = BaseSeeder()
    extractor = BaseExtractor()
    miner = BaseMiner()

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

        if self.status == self.Status.SEEDED and next_status == self.Status.EXTRACTED:
            if not self.text_data and not self.blob_data:
                raise TransitionError("Cannot transition to EXTRACTED without data")

            self.last_error = ""
            self.status = next_status
            self.extracted_at = timezone.now()
        elif self.status == self.Status.EXTRACTED and next_status == self.Status.MINED:
            self.last_error = ""
            self.status = next_status
            self.mined_at = timezone.now()
        else:
            raise TransitionError(
                f"Cannot transition from {self.status} to {next_status}"
            )

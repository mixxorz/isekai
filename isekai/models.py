from django.contrib.contenttypes.fields import GenericForeignKey
from django.contrib.contenttypes.models import ContentType
from django.db import models


class AbstractResource(models.Model):
    class Status(models.TextChoices):
        SEEDED = "seeded", "Seeded"
        EXTRACTED = "extracted", "Extracted"
        MINED = "mined", "Mined"
        TRANSFORMED = "transformed", "Transformed"
        LOADED = "loaded", "Loaded"

    key = models.CharField(max_length=255, primary_key=True, db_index=True)
    mime_type = models.CharField(max_length=100, blank=True)
    data_type = models.CharField(
        max_length=10,
        choices=[("text", "Text"), ("blob", "Blob")],
        blank=True,
    )
    blob_data = models.FileField(upload_to="resources/", blank=True, null=True)
    text_data = models.TextField(
        blank=True,
    )
    target_content_type = models.ForeignKey(
        ContentType, on_delete=models.CASCADE, blank=True, null=True
    )
    target_object_id = models.PositiveIntegerField(blank=True, null=True)
    target_object = GenericForeignKey("target_content_type", "target_object_id")
    target_spec = models.JSONField(blank=True, null=True)
    status = models.CharField(
        max_length=20,
        choices=Status.choices,
        blank=True,
    )

    # Audit fields for status transitions
    seeded_at = models.DateTimeField(auto_now_add=True, null=True)
    extracted_at = models.DateTimeField(blank=True, null=True)
    mined_at = models.DateTimeField(blank=True, null=True)
    transformed_at = models.DateTimeField(blank=True, null=True)
    loaded_at = models.DateTimeField(blank=True, null=True)

    # Error tracking
    last_error = models.TextField(blank=True)

    class Meta:
        abstract = True

    @property
    def data(self):
        if self.data_type == "text":
            return self.text_data
        elif self.data_type == "blob":
            return self.blob_data
        return None

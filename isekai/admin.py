from django.contrib import admin

from isekai.models import AbstractResource


def set_status_to_extracted(modeladmin, request, queryset):
    """Set selected resources to EXTRACTED status."""
    updated = queryset.update(status=AbstractResource.Status.EXTRACTED)
    modeladmin.message_user(request, f"{updated} resources marked as EXTRACTED.")


set_status_to_extracted.short_description = "Mark as EXTRACTED"


class AbstractResourceAdmin(admin.ModelAdmin):
    list_display = [
        "key",
        "status",
        "data_type",
        "mime_type",
        "target_content_type",
        "seeded_at",
        "extracted_at",
        "mined_at",
        "transformed_at",
        "loaded_at",
    ]
    filter_horizontal = ["dependencies"]
    actions = [set_status_to_extracted]
    list_filter = [
        "status",
        "data_type",
        "mime_type",
        "target_content_type",
        "seeded_at",
    ]
    search_fields = ["key", "mime_type"]
    readonly_fields = [
        "seeded_at",
        "extracted_at",
        "mined_at",
        "transformed_at",
        "loaded_at",
    ]
    fieldsets = [
        (None, {"fields": ["key", "status", "last_error"]}),
        (
            "Data",
            {
                "fields": [
                    "data_type",
                    "mime_type",
                    "text_data",
                    "blob_data",
                    "metadata",
                ]
            },
        ),
        (
            "Dependencies",
            {
                "fields": ["dependencies"],
                "classes": ["collapse"],
            },
        ),
        (
            "Target",
            {
                "fields": ["target_content_type", "target_object_id", "target_spec"],
                "classes": ["collapse"],
            },
        ),
        (
            "Audit",
            {
                "fields": [
                    "seeded_at",
                    "extracted_at",
                    "mined_at",
                    "transformed_at",
                    "loaded_at",
                ],
                "classes": ["collapse"],
            },
        ),
    ]

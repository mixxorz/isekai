from django.contrib import admin


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
        ("Data", {"fields": ["data_type", "mime_type", "text_data", "blob_data"]}),
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

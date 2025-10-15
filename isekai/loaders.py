import uuid

from django.apps import apps
from django.core.files import File
from django.core.files.base import ContentFile
from django.db import connection, models, transaction
from django.utils import timezone
from modelcluster.fields import ParentalKey, ParentalManyToManyField

from isekai.types import BaseRef, BlobRef, Key, ModelRef, Resolver, ResourceRef, Spec


class BaseLoader:
    def load(
        self, specs: list[tuple[Key, Spec]], resolver: Resolver
    ) -> list[tuple[Key, models.Model]]:
        return []


class ModelLoader(BaseLoader):
    def load(
        self, specs: list[tuple[Key, Spec]], resolver: Resolver
    ) -> list[tuple[Key, models.Model]]:
        """Creates Django objects from (Key, Spec) tuples with cross-references."""
        if not specs:
            return []

        # Build lookup maps
        key_to_spec = dict(specs)
        key_to_model = {
            key: self._get_model_class(spec.content_type) for key, spec in specs
        }
        key_to_temp_fk = self._build_temp_fk_mapping(specs, key_to_model)

        # Track state
        key_to_object = {}
        created_objects = []
        pending_refs = []  # For all ResourceRef to internal resources
        pending_m2ms = []

        with transaction.atomic(), connection.constraint_checks_disabled():
            # Create all objects
            for key, spec in specs:
                obj = self._create_object(
                    key,
                    spec,
                    key_to_model[key],
                    key_to_spec,
                    key_to_temp_fk,
                    pending_refs,
                    pending_m2ms,
                    resolver,
                )
                key_to_object[key] = obj
                created_objects.append((key, obj))

            # Resolve all pending internal ResourceRef
            for obj_key, field_name, ref in pending_refs:
                # Get the referenced object
                referenced_obj = key_to_object[ref.key]
                # Traverse attribute path if present
                value = referenced_obj
                for attr in ref.attr_path:
                    value = getattr(value, attr)
                # Set the field value
                setattr(key_to_object[obj_key], field_name, value)
                key_to_object[obj_key].save()

            # Update JSON fields with resolved refs
            for key, spec in specs:
                self._update_json_fields(
                    key_to_object[key], spec, key_to_object, resolver
                )

            # Set M2M relationships
            for obj_key, field_name, ref_values in pending_m2ms:
                m2m_manager = getattr(key_to_object[obj_key], field_name)
                resolved_values = []
                for ref in ref_values:
                    if isinstance(ref, ResourceRef):
                        if ref.key in key_to_object:
                            resolved_values.append(key_to_object[ref.key])
                        else:
                            resolved_values.append(resolver(ref))
                    elif isinstance(ref, ModelRef):
                        # ModelRef always references external objects
                        resolved_values.append(resolver(ref))
                    else:
                        resolved_values.append(ref)
                m2m_manager.set(resolved_values)

            connection.check_constraints()

        return created_objects

    def _get_model_class(self, content_type: str):
        """Get model class from content_type string (always app_label.Model format)."""
        app_label, model_name = content_type.split(".", 1)
        return apps.get_model(app_label, model_name)

    def _build_temp_fk_mapping(self, specs, key_to_model):
        """Build temporary FK values for cross-references."""
        key_to_temp_fk = {}
        temp_id = -1000000

        for key, _ in specs:
            model_class = key_to_model[key]
            pk_field = model_class._meta.pk

            if pk_field.get_internal_type() == "UUIDField":
                key_to_temp_fk[key] = uuid.uuid4()
            else:
                key_to_temp_fk[key] = temp_id
                temp_id -= 1

        return key_to_temp_fk

    def _get_temp_value_for_field(self, field, ref_key, key_to_temp_fk):
        """Generate appropriate temporary value based on field type."""
        field_type = field.get_internal_type()

        # FK fields use the temp PK mapping
        if field_type in ("ForeignKey", "OneToOneField"):
            return key_to_temp_fk[ref_key]

        # Integer fields
        if field_type in (
            "IntegerField",
            "PositiveIntegerField",
            "BigIntegerField",
            "SmallIntegerField",
        ):
            return -999999

        # String fields
        if field_type in (
            "CharField",
            "TextField",
            "EmailField",
            "URLField",
            "SlugField",
        ):
            return "temp_value"

        # Boolean fields
        if field_type == "BooleanField":
            return False

        # Date/Time fields
        if field_type == "DateTimeField":
            return timezone.now()
        if field_type == "DateField":
            return timezone.now().date()
        if field_type == "TimeField":
            return timezone.now().time()

        # Numeric fields
        if field_type in ("FloatField", "DecimalField"):
            return -999.999

        # UUID fields
        if field_type == "UUIDField":
            return uuid.uuid4()

        # For nullable fields or unknown types, return None
        return None

    def _create_object(
        self,
        key,
        spec,
        model_class,
        key_to_spec,
        key_to_temp_fk,
        pending_refs,
        pending_m2ms,
        resolver,
    ):
        """Create a single object with processed fields."""
        # Build field mapping
        model_fields = {
            f.name: f
            for f in model_class._meta.get_fields()
            if hasattr(f, "contribute_to_class")
        }

        # Add _id accessor fields for FK/OneToOne fields so we can look them up
        fk_fields = {
            field_name: field
            for field_name, field in model_fields.items()
            if isinstance(field, models.ForeignKey | models.OneToOneField | ParentalKey)
        }
        for field_name, field in fk_fields.items():
            model_fields[f"{field_name}_id"] = field

        obj_fields = {}

        # Set UUID PK if needed
        if isinstance(key_to_temp_fk[key], uuid.UUID):
            obj_fields["pk"] = key_to_temp_fk[key]

        # Process each field
        for field_name, field_value in spec.attributes.items():
            field = model_fields[field_name]

            if isinstance(field_value, BlobRef):
                # Handle blob fields immediately
                file_ref = resolver(field_value)
                with file_ref.open() as f:
                    obj_fields[field_name] = File(ContentFile(f.read()), file_ref.name)

            elif isinstance(field_value, ResourceRef):
                if field_value.key in key_to_spec:
                    # Internal ref - defer resolution until after all objects are created
                    # Set appropriate temp value for ANY field type to satisfy NOT NULL
                    temp_value = self._get_temp_value_for_field(
                        field, field_value.key, key_to_temp_fk
                    )
                    if temp_value is not None:
                        obj_fields[field_name] = temp_value
                    # Mark for later resolution
                    pending_refs.append((key, field_name, field_value))
                else:
                    # External ref - resolve immediately
                    obj_fields[field_name] = resolver(field_value)

            elif isinstance(field_value, ModelRef):
                # ModelRef always references external DB objects, never internal refs
                # Resolve immediately for FK fields; skip for JSON fields (resolved later)
                if field.get_internal_type() == "JSONField":
                    # JSON field - skip for now, will be resolved in JSON phase
                    pass
                else:
                    # Resolve immediately - let Django handle validation if wrong field type
                    obj_fields[field_name] = resolver(field_value)

            elif isinstance(field_value, list) and any(
                isinstance(v, BaseRef | ResourceRef | ModelRef) for v in field_value
            ):
                if isinstance(field, models.ManyToManyField | ParentalManyToManyField):
                    # M2M fields accept both ResourceRef and ModelRef
                    # This matches Django's behavior where m2m.set() accepts both PKs and instances
                    pending_m2ms.append((key, field_name, field_value))
                else:
                    # List with refs in non-M2M field (likely JSON) - skip for now
                    pass

            else:
                # Regular field - but skip JSON fields with refs since reference objects aren't JSON serializable
                if field.get_internal_type() == "JSONField" and self._has_refs(
                    field_value
                ):
                    pass  # Will be resolved and saved in JSON phase after all objects exist
                else:
                    obj_fields[field_name] = field_value

        return self._save_object(model_class, obj_fields)

    def _save_object(self, model_class, obj_fields):
        """Save the object to the database."""
        obj = model_class(**obj_fields)
        obj.save()
        return obj

    def _update_json_fields(self, obj, spec, key_to_object, resolver):
        """Update JSON fields with resolved references."""
        json_fields = [
            f for f in obj._meta.get_fields() if f.get_internal_type() == "JSONField"
        ]

        updated = False
        for json_field in json_fields:
            if json_field.name in spec.attributes:
                field_value = spec.attributes[json_field.name]
                # Always try to resolve - _resolve_refs returns unchanged if no refs
                resolved_value = self._resolve_refs(
                    field_value, key_to_object, resolver
                )
                if resolved_value != field_value:  # Only update if something changed
                    setattr(obj, json_field.name, resolved_value)
                    updated = True

        if updated:
            obj.save()

    def _has_refs(self, data):
        """Check if data contains reference objects."""
        if isinstance(data, BaseRef | ResourceRef | ModelRef):
            return True
        elif isinstance(data, dict):
            return any(self._has_refs(v) for v in data.values())
        elif isinstance(data, list):
            return any(self._has_refs(item) for item in data)
        return False

    def _resolve_refs(self, data, key_to_object, resolver):
        """Recursively resolve ResourceRef and ModelRef objects in nested data.

        For JSON fields, refs are resolved to their PK values (not model instances)
        since JSON fields can only store serializable data.
        """
        if isinstance(data, ResourceRef):
            # Resolve to model instance first, then extract PK
            obj = (
                key_to_object[data.key] if data.key in key_to_object else resolver(data)
            )
            return obj.pk
        elif isinstance(data, ModelRef):
            # ModelRef always references external objects, resolve to PK
            obj = resolver(data)
            return obj.pk
        elif isinstance(data, dict):
            return {
                k: self._resolve_refs(v, key_to_object, resolver)
                for k, v in data.items()
            }
        elif isinstance(data, list):
            return [self._resolve_refs(item, key_to_object, resolver) for item in data]
        else:
            return data

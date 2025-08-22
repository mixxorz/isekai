import uuid

from django.apps import apps
from django.core.files import File
from django.core.files.base import ContentFile
from django.db import connection, models, transaction
from modelcluster.fields import ParentalKey, ParentalManyToManyField

from isekai.types import BlobRef, Key, Ref, Resolver, Spec


class BaseLoader:
    def __init__(self, resolver: Resolver):
        self.resolve = resolver

    def load(self, specs: list[tuple[Key, Spec]]) -> list[models.Model]:
        return []


class ModelLoader(BaseLoader):
    def load(self, specs: list[tuple[Key, Spec]]) -> list[models.Model]:
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
        pending_fks = []
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
                    pending_fks,
                    pending_m2ms,
                )
                key_to_object[key] = obj
                created_objects.append(obj)

            # Fix FK references
            for obj_key, field_name, ref_key in pending_fks:
                setattr(key_to_object[obj_key], field_name, key_to_object[ref_key].pk)
                key_to_object[obj_key].save()

            # Update JSON fields with resolved refs
            for key, spec in specs:
                self._update_json_fields(key_to_object[key], spec, key_to_object)

            # Set M2M relationships
            for obj_key, field_name, ref_values in pending_m2ms:
                m2m_manager = getattr(key_to_object[obj_key], field_name)
                resolved_ids = []
                for ref in ref_values:
                    if isinstance(ref, Ref):
                        if ref.key in key_to_object:
                            resolved_ids.append(key_to_object[ref.key].pk)
                        else:
                            resolved_ids.append(self.resolve(ref))
                    else:
                        resolved_ids.append(ref)
                m2m_manager.set(resolved_ids)

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

    def _create_object(
        self,
        key,
        spec,
        model_class,
        key_to_spec,
        key_to_temp_fk,
        pending_fks,
        pending_m2ms,
    ):
        """Create a single object with processed fields."""
        model_fields = {
            f.name: f
            for f in model_class._meta.get_fields()
            if hasattr(f, "contribute_to_class")
        }

        obj_fields = {}

        # Set UUID PK if needed
        if isinstance(key_to_temp_fk[key], uuid.UUID):
            obj_fields["pk"] = key_to_temp_fk[key]

        # Process each field
        for field_name, field_value in spec.attributes.items():
            field = model_fields.get(field_name)

            if isinstance(field_value, BlobRef):
                # Handle blob fields immediately
                file_ref = self.resolve(field_value)
                with file_ref.open() as f:
                    obj_fields[field_name] = File(ContentFile(f.read()), file_ref.name)

            elif isinstance(field_value, Ref):
                if field and isinstance(field, models.ForeignKey | ParentalKey):
                    if field_value.key in key_to_spec:
                        # Internal ref - use temp value, schedule for update
                        obj_fields[f"{field_name}_id"] = key_to_temp_fk[field_value.key]
                        pending_fks.append((key, f"{field_name}_id", field_value.key))
                    else:
                        # External ref - resolve immediately
                        obj_fields[f"{field_name}_id"] = self.resolve(field_value)
                else:
                    # Ref in non-FK field (likely JSON) - skip for now
                    pass

            elif isinstance(field_value, list) and any(
                isinstance(v, Ref) for v in field_value
            ):
                if field and isinstance(
                    field, models.ManyToManyField | ParentalManyToManyField
                ):
                    pending_m2ms.append((key, field_name, field_value))
                else:
                    # List with refs in non-M2M field (likely JSON) - skip for now
                    pass

            else:
                # Regular field - but skip JSON fields with refs since Ref objects aren't JSON serializable
                if (
                    field
                    and isinstance(field, models.JSONField)
                    and self._has_refs(field_value)
                ):
                    pass  # Will be resolved and saved in JSON phase after all objects exist
                else:
                    obj_fields[field_name] = field_value

        # Create object with all processed fields
        obj = model_class(**obj_fields)
        obj.save()
        return obj

    def _update_json_fields(self, obj, spec, key_to_object):
        """Update JSON fields with resolved references."""
        json_fields = [
            f for f in obj._meta.get_fields() if isinstance(f, models.JSONField)
        ]

        updated = False
        for json_field in json_fields:
            if json_field.name in spec.attributes:
                field_value = spec.attributes[json_field.name]
                # Always try to resolve - _resolve_refs returns unchanged if no refs
                resolved_value = self._resolve_refs(field_value, key_to_object)
                if resolved_value != field_value:  # Only update if something changed
                    setattr(obj, json_field.name, resolved_value)
                    updated = True

        if updated:
            obj.save()

    def _has_refs(self, data):
        """Check if data contains Ref objects."""
        if isinstance(data, Ref):
            return True
        elif isinstance(data, dict):
            return any(self._has_refs(v) for v in data.values())
        elif isinstance(data, list):
            return any(self._has_refs(item) for item in data)
        return False

    def _resolve_refs(self, data, key_to_object):
        """Recursively resolve Ref objects in nested data."""
        if isinstance(data, Ref):
            return (
                key_to_object[data.key].pk
                if data.key in key_to_object
                else self.resolve(data)
            )
        elif isinstance(data, dict):
            return {k: self._resolve_refs(v, key_to_object) for k, v in data.items()}
        elif isinstance(data, list):
            return [self._resolve_refs(item, key_to_object) for item in data]
        else:
            return data

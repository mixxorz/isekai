import uuid

from django.apps import apps
from django.core.files import File
from django.core.files.base import ContentFile
from django.db import connection, models, transaction
from modelcluster.fields import ParentalKey, ParentalManyToManyField

from isekai.types import BaseRef, BlobRef, Key, ModelRef, PkRef, Resolver, Spec


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
        pending_fks = []  # For PkRef in _id fields
        pending_fk_instances = []  # For ModelRef in FK fields
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
                    pending_fk_instances,
                    pending_m2ms,
                    resolver,
                )
                key_to_object[key] = obj
                created_objects.append((key, obj))

            # Fix FK ID references (PkRef in _id fields)
            for obj_key, field_name, ref_key in pending_fks:
                setattr(key_to_object[obj_key], field_name, key_to_object[ref_key].pk)
                key_to_object[obj_key].save()

            # Fix FK instance references (ModelRef in FK fields)
            for obj_key, field_name, ref_key in pending_fk_instances:
                setattr(key_to_object[obj_key], field_name, key_to_object[ref_key])
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
                    if isinstance(ref, PkRef):
                        if ref.key in key_to_object:
                            resolved_values.append(key_to_object[ref.key].pk)
                        else:
                            resolved_values.append(resolver(ref))
                    elif isinstance(ref, ModelRef):
                        if ref.key in key_to_object:
                            resolved_values.append(key_to_object[ref.key])
                        else:
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

    def _create_object(
        self,
        key,
        spec,
        model_class,
        key_to_spec,
        key_to_temp_fk,
        pending_fks,
        pending_fk_instances,
        pending_m2ms,
        resolver,
    ):
        """Create a single object with processed fields."""
        # Build comprehensive field mapping including _id fields for FKs
        model_fields = {
            f.name: f
            for f in model_class._meta.get_fields()
            if hasattr(f, "contribute_to_class")
        }

        # Add _id mappings for FK/OneToOne fields
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
            field = model_fields.get(field_name)

            if isinstance(field_value, BlobRef):
                # Handle blob fields immediately
                file_ref = resolver(field_value)
                with file_ref.open() as f:
                    obj_fields[field_name] = File(ContentFile(f.read()), file_ref.name)

            elif isinstance(field_value, PkRef):
                if field and isinstance(
                    field, models.ForeignKey | models.OneToOneField | ParentalKey
                ):
                    if field_name.endswith("_id"):
                        # PkRef in FK ID field (e.g., author_id) - use PK value directly
                        if field_value.key in key_to_spec:
                            # Internal ref - use temp value, schedule for update
                            obj_fields[field_name] = key_to_temp_fk[field_value.key]
                            pending_fks.append((key, field_name, field_value.key))
                        else:
                            # External ref - resolve immediately
                            obj_fields[field_name] = resolver(field_value)
                    else:
                        # PkRef in FK field (e.g., author) - Django expects model instance, not PK
                        raise ValueError(
                            f"PkRef not allowed in FK field {field_name}. Use ModelRef for FK fields or PkRef with {field_name}_id."
                        )
                else:
                    # PkRef in non-FK field (likely JSON) - skip for now
                    pass

            elif isinstance(field_value, ModelRef):
                if field and isinstance(
                    field, models.ForeignKey | models.OneToOneField | ParentalKey
                ):
                    if field_name.endswith("_id"):
                        # ModelRef in FK ID field - Django expects PK value, not instance
                        raise ValueError(
                            f"ModelRef not allowed in FK ID field {field_name}. Use PkRef for _id fields."
                        )
                    else:
                        # ModelRef in FK field (e.g., author) - Django expects model instance
                        if field_value.key in key_to_spec:
                            # Internal ref - will be resolved after all objects are created
                            pending_fk_instances.append(
                                (key, field_name, field_value.key)
                            )
                            # Don't set the field now - will be set later
                        else:
                            # External ref - resolve immediately to model instance
                            obj_fields[field_name] = resolver(field_value)
                else:
                    # ModelRef in non-FK field (likely JSON) - skip for now, will be resolved later
                    pass

            elif isinstance(field_value, list) and any(
                isinstance(v, BaseRef) for v in field_value
            ):
                if field and isinstance(
                    field, models.ManyToManyField | ParentalManyToManyField
                ):
                    # M2M fields accept both PkRef (for PK values) and ModelRef (for instances)
                    # This matches Django's behavior where m2m.set() accepts both
                    pending_m2ms.append((key, field_name, field_value))
                else:
                    # List with refs in non-M2M field (likely JSON) - skip for now
                    pass

            else:
                # Regular field - but skip JSON fields with refs since reference objects aren't JSON serializable
                if (
                    field
                    and field.get_internal_type() == "JSONField"
                    and self._has_refs(field_value)
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
        if isinstance(data, BaseRef):
            return True
        elif isinstance(data, dict):
            return any(self._has_refs(v) for v in data.values())
        elif isinstance(data, list):
            return any(self._has_refs(item) for item in data)
        return False

    def _resolve_refs(self, data, key_to_object, resolver):
        """Recursively resolve PkRef and ModelRef objects in nested data."""
        if isinstance(data, PkRef):
            return (
                key_to_object[data.key].pk
                if data.key in key_to_object
                else resolver(data)
            )
        elif isinstance(data, ModelRef):
            return (
                key_to_object[data.key] if data.key in key_to_object else resolver(data)
            )
        elif isinstance(data, dict):
            return {
                k: self._resolve_refs(v, key_to_object, resolver)
                for k, v in data.items()
            }
        elif isinstance(data, list):
            return [self._resolve_refs(item, key_to_object, resolver) for item in data]
        else:
            return data

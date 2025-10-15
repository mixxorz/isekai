from django.db import models
from wagtail.models import Page

from isekai.loaders import ModelLoader
from isekai.types import Key, Resolver, ResourceRef, Spec


class PageLoader(ModelLoader):
    _parent_page_prefix = "__wagtail_parent_page"

    def load(
        self, specs: list[tuple[Key, Spec]], resolver: Resolver
    ) -> list[tuple[Key, models.Model]]:
        # Check if any of the specs are for Wagtail Page models
        if not any(spec.attributes.get(self._parent_page_prefix) for _, spec in specs):
            # If not, let another loader handle it
            return []

        page_specs = [
            (key, spec)
            for key, spec in specs
            if spec.attributes.get(self._parent_page_prefix)
        ]

        key_to_parent_page_ref = {}

        for key, spec in page_specs:
            # Remove the parent page attribute after capturing it
            # so that ModelLoader doesn't try to process it
            parent_page_ref_or_id = spec.attributes.pop(self._parent_page_prefix)
            key_to_parent_page_ref[key] = parent_page_ref_or_id

        # Let ModelLoader create the pages first
        created_objects = super().load(specs, resolver)

        # Move the created pages to their actual parent pages
        key_to_page = {
            key: obj for key, obj in created_objects if isinstance(obj, Page)
        }

        for key, _ in page_specs:
            page = key_to_page[key]
            parent_page_ref_or_id = key_to_parent_page_ref[key]

            # If the reference passed is an ID, we can fetch the page directly
            # If it's a ref, we can check if it's in this batch
            # If not, we can use resolver
            if isinstance(parent_page_ref_or_id, int):
                parent_page = Page.objects.get(pk=parent_page_ref_or_id)
            elif isinstance(parent_page_ref_or_id, ResourceRef):
                parent_ref = parent_page_ref_or_id
                if parent_ref.key in key_to_page:
                    parent_page = key_to_page[parent_ref.key]
                else:
                    # Resolve to get the parent model instance
                    resolved_parent = resolver(parent_ref)
                    # Fetch a fresh Page instance from DB to ensure tree fields are correct
                    parent_page = Page.objects.get(pk=resolved_parent.pk)
            else:
                raise ValueError(
                    f"Invalid {self._parent_page_prefix} value: {parent_page_ref_or_id}"
                )

            page.move(parent_page, pos="last-child")

        return created_objects

    def _save_object(self, model_class, obj_fields):
        """Save the object to the database."""
        # Wagtail should only have one root page
        root_page = getattr(self, "_root_page", Page.get_root_nodes().get())
        self._root_page = root_page
        assert isinstance(root_page, Page)

        obj = model_class(**obj_fields)
        root_page.add_child(instance=obj)
        return obj

from isekai.types import (
    BlobRef,
    Key,
    ModelRef,
    ResourceRef,
    Spec,
    ref,
)
from tests.test_models import pytest


class TestKey:
    def test_key(self):
        key = Key(type="test", value="123")
        assert str(key) == "test:123"

        # Key from string
        key_from_string = Key.from_string("test:123")
        assert key_from_string == key

    def test_invalid_key_string(self):
        # Invalid format should raise ValueError
        with pytest.raises(ValueError):
            Key.from_string("invalid-key")

        # No value should raise ValueError
        with pytest.raises(ValueError):
            Key.from_string("test:")


class TestRefs:
    def test_blob_ref(self):
        key = Key(type="blob", value="456")

        # Key to BlobRef
        blob_ref = BlobRef(key)
        assert str(blob_ref) == "isekai-blob-ref:\\blob:456"

        # BlobRef to Key
        blob_ref = BlobRef.from_string("isekai-blob-ref:\\blob:456")
        assert blob_ref.key == key

    def test_blob_ref_invalid_string(self):
        # Invalid format should raise ValueError
        with pytest.raises(ValueError):
            BlobRef.from_string("invalid-blob-string")

        # Invalid prefix should raise ValueError
        with pytest.raises(ValueError):
            BlobRef.from_string("blob:\\test:456")

    def test_resource_ref_basic(self):
        key = Key(type="user", value="123")

        # Basic ResourceRef without attribute access
        ref = ResourceRef(key)
        assert str(ref) == "isekai-resource-ref:\\user:123"

        # ResourceRef from string
        ref = ResourceRef.from_string("isekai-resource-ref:\\user:123")
        assert ref.key == key
        assert ref.ref_attr_path == ()

    def test_resource_ref_with_pk_attribute(self):
        key = Key(type="user", value="123")

        # ResourceRef with .pk access
        ref = ResourceRef(key).pk
        assert str(ref) == "isekai-resource-ref:\\user:123::pk"

        # ResourceRef from string with pk
        ref = ResourceRef.from_string("isekai-resource-ref:\\user:123::pk")
        assert ref.key == key
        assert ref.ref_attr_path == ("pk",)

    def test_resource_ref_with_chained_attributes(self):
        key = Key(type="user", value="123")

        # ResourceRef with chained attribute access
        ref = ResourceRef(key).group.name
        assert str(ref) == "isekai-resource-ref:\\user:123::group.name"

        # ResourceRef from string with chained attributes
        ref = ResourceRef.from_string("isekai-resource-ref:\\user:123::group.name")
        assert ref.key == key
        assert ref.ref_attr_path == ("group", "name")

    def test_resource_ref_with_deep_chaining(self):
        key = Key(type="article", value="456")

        # ResourceRef with deep chaining
        ref = ResourceRef(key).author.group.name.slug
        assert str(ref) == "isekai-resource-ref:\\article:456::author.group.name.slug"

        # ResourceRef from string with deep chaining
        ref = ResourceRef.from_string(
            "isekai-resource-ref:\\article:456::author.group.name.slug"
        )
        assert ref.key == key
        assert ref.ref_attr_path == ("author", "group", "name", "slug")

    def test_resource_ref_invalid_string(self):
        # Invalid format should raise ValueError
        with pytest.raises(ValueError):
            ResourceRef.from_string("invalid-string")

        # Invalid prefix should raise ValueError
        with pytest.raises(ValueError):
            ResourceRef.from_string("resource:\\test:123")

    def test_model_ref_basic(self):
        # Basic ModelRef with single kwarg
        ref = ModelRef("testapp.Author", pk=42)
        assert str(ref) == "isekai-model-ref:\\testapp.Author?pk=42"

        # ModelRef from string
        ref = ModelRef.from_string("isekai-model-ref:\\testapp.Author?pk=42")
        assert ref.ref_content_type == "testapp.Author"
        assert ref.ref_lookup_kwargs == {"pk": "42"}
        assert ref.ref_attr_path == ()

    def test_model_ref_multiple_kwargs(self):
        # ModelRef with multiple kwargs
        ref = ModelRef("auth.User", email="test@example.com", is_active=True)
        ref_str = str(ref)
        assert ref_str.startswith("isekai-model-ref:\\auth.User?")
        # Query params can be in any order, so check both contain the same params
        assert "email=test%40example.com" in ref_str
        assert "is_active=True" in ref_str

        # ModelRef from string with multiple params
        ref = ModelRef.from_string(
            "isekai-model-ref:\\auth.User?email=test%40example.com&is_active=True"
        )
        assert ref.ref_content_type == "auth.User"
        assert ref.ref_lookup_kwargs == {
            "email": "test@example.com",
            "is_active": "True",
        }

    def test_model_ref_with_attribute_access(self):
        # ModelRef with attribute access
        ref = ModelRef("testapp.Author", pk=42).group.name
        assert str(ref) == "isekai-model-ref:\\testapp.Author?pk=42::group.name"

        # ModelRef from string with attributes
        ref = ModelRef.from_string(
            "isekai-model-ref:\\testapp.Author?pk=42::group.name"
        )
        assert ref.ref_content_type == "testapp.Author"
        assert ref.ref_lookup_kwargs == {"pk": "42"}
        assert ref.ref_attr_path == ("group", "name")

    def test_model_ref_with_deep_chaining(self):
        # ModelRef with deep attribute chaining
        ref = ModelRef("testapp.Article", slug="my-article").author.group.name
        ref_str = str(ref)
        assert ref_str.startswith("isekai-model-ref:\\testapp.Article?")
        assert "slug=my-article" in ref_str
        assert ref_str.endswith("::author.group.name")

        # ModelRef from string with deep chaining
        ref = ModelRef.from_string(
            "isekai-model-ref:\\testapp.Article?slug=my-article::author.group.name"
        )
        assert ref.ref_content_type == "testapp.Article"
        assert ref.ref_lookup_kwargs == {"slug": "my-article"}
        assert ref.ref_attr_path == ("author", "group", "name")

    def test_model_ref_with_pk_attribute(self):
        # ModelRef with .pk access
        ref = ModelRef("testapp.Author", email="test@example.com").pk
        assert (
            str(ref) == "isekai-model-ref:\\testapp.Author?email=test%40example.com::pk"
        )

        # ModelRef from string with pk
        ref = ModelRef.from_string(
            "isekai-model-ref:\\testapp.Author?email=test%40example.com::pk"
        )
        assert ref.ref_content_type == "testapp.Author"
        assert ref.ref_lookup_kwargs == {"email": "test@example.com"}
        assert ref.ref_attr_path == ("pk",)

    def test_model_ref_invalid_string(self):
        # Invalid format should raise ValueError
        with pytest.raises(ValueError):
            ModelRef.from_string("invalid-string")

        # Invalid prefix should raise ValueError
        with pytest.raises(ValueError):
            ModelRef.from_string("model:\\testapp.Author?pk=42")


class TestSpec:
    def test_to_dict(self):
        spec = Spec(
            content_type="foo.Bar",
            attributes={
                "title": "Test Title",
                "image": BlobRef(
                    Key(type="url", value="https://example.com/image.png")
                ),
                "description": "A sample description",
                "call_to_action": ResourceRef(
                    Key(type="gen", value="call_to_action_123")
                ).pk,
                "child_object": {
                    "pk": ResourceRef(Key(type="gen", value="child_object_456")).pk,
                    "name": "Child Object Name",
                },
            },
        )

        expected_dict = {
            "content_type": "foo.Bar",
            "attributes": {
                "title": "Test Title",
                "image": "isekai-blob-ref:\\url:https://example.com/image.png",
                "description": "A sample description",
                "call_to_action": "isekai-resource-ref:\\gen:call_to_action_123::pk",
                "child_object": {
                    "pk": "isekai-resource-ref:\\gen:child_object_456::pk",
                    "name": "Child Object Name",
                },
            },
        }

        assert spec.to_dict() == expected_dict

    def test_to_dict_with_lists(self):
        spec = Spec(
            content_type="foo.ListContainer",
            attributes={
                "images": [
                    BlobRef(Key(type="file", value="image1.jpg")),
                    BlobRef(Key(type="file", value="image2.jpg")),
                ],
                "references": [
                    ResourceRef(Key(type="gen", value="ref1")).pk,
                    ResourceRef(Key(type="gen", value="ref2")).pk,
                ],
                "mixed_list": [
                    "string_value",
                    42,
                    ResourceRef(Key(type="gen", value="mixed_ref")).pk,
                    {"nested_ref": BlobRef(Key(type="url", value="nested.png"))},
                ],
            },
        )

        expected_dict = {
            "content_type": "foo.ListContainer",
            "attributes": {
                "images": [
                    "isekai-blob-ref:\\file:image1.jpg",
                    "isekai-blob-ref:\\file:image2.jpg",
                ],
                "references": [
                    "isekai-resource-ref:\\gen:ref1::pk",
                    "isekai-resource-ref:\\gen:ref2::pk",
                ],
                "mixed_list": [
                    "string_value",
                    42,
                    "isekai-resource-ref:\\gen:mixed_ref::pk",
                    {"nested_ref": "isekai-blob-ref:\\url:nested.png"},
                ],
            },
        }

        assert spec.to_dict() == expected_dict

    def test_to_dict_with_tuples(self):
        spec = Spec(
            content_type="foo.TupleContainer",
            attributes={
                "tuple_refs": (
                    ResourceRef(Key(type="gen", value="tuple_ref1")).pk,
                    BlobRef(Key(type="file", value="tuple_blob.jpg")),
                    "tuple_string",
                ),
            },
        )

        expected_dict = {
            "content_type": "foo.TupleContainer",
            "attributes": {
                "tuple_refs": [
                    "isekai-resource-ref:\\gen:tuple_ref1::pk",
                    "isekai-blob-ref:\\file:tuple_blob.jpg",
                    "tuple_string",
                ],
            },
        }

        assert spec.to_dict() == expected_dict

    def test_to_dict_deeply_nested(self):
        spec = Spec(
            content_type="foo.DeepNested",
            attributes={
                "level1": {
                    "level2": {
                        "level3": {
                            "deep_ref": ResourceRef(
                                Key(type="deep", value="nested_value")
                            ).pk,
                            "deep_list": [
                                BlobRef(Key(type="nested", value="deep_blob.png")),
                                {
                                    "even_deeper": ResourceRef(
                                        Key(type="deepest", value="bottom")
                                    ).pk
                                },
                            ],
                        },
                    },
                },
            },
        )

        expected_dict = {
            "content_type": "foo.DeepNested",
            "attributes": {
                "level1": {
                    "level2": {
                        "level3": {
                            "deep_ref": "isekai-resource-ref:\\deep:nested_value::pk",
                            "deep_list": [
                                "isekai-blob-ref:\\nested:deep_blob.png",
                                {
                                    "even_deeper": "isekai-resource-ref:\\deepest:bottom::pk"
                                },
                            ],
                        },
                    },
                },
            },
        }

        assert spec.to_dict() == expected_dict

    def test_to_dict_empty_attributes(self):
        spec = Spec(
            content_type="foo.Empty",
            attributes={},
        )

        expected_dict = {
            "content_type": "foo.Empty",
            "attributes": {},
        }

        assert spec.to_dict() == expected_dict

    def test_to_dict_none_values(self):
        spec = Spec(
            content_type="foo.WithNone",
            attributes={
                "none_value": None,
                "ref_with_none": ResourceRef(Key(type="gen", value="has_none")).pk,
                "dict_with_none": {
                    "inner_none": None,
                    "inner_ref": BlobRef(Key(type="file", value="none_test.jpg")),
                },
                "list_with_none": [
                    None,
                    ResourceRef(Key(type="gen", value="in_list")).pk,
                ],
            },
        )

        expected_dict = {
            "content_type": "foo.WithNone",
            "attributes": {
                "none_value": None,
                "ref_with_none": "isekai-resource-ref:\\gen:has_none::pk",
                "dict_with_none": {
                    "inner_none": None,
                    "inner_ref": "isekai-blob-ref:\\file:none_test.jpg",
                },
                "list_with_none": [None, "isekai-resource-ref:\\gen:in_list::pk"],
            },
        }

        assert spec.to_dict() == expected_dict

    def test_from_dict_basic(self):
        data = {
            "content_type": "foo.Bar",
            "attributes": {
                "title": "Test Title",
                "image": "isekai-blob-ref:\\url:https://example.com/image.png",
                "description": "A sample description",
                "call_to_action": "isekai-resource-ref:\\gen:call_to_action_123::pk",
                "child_object": {
                    "pk": "isekai-resource-ref:\\gen:child_object_456::pk",
                    "name": "Child Object Name",
                },
            },
        }

        spec = Spec.from_dict(data)

        expected_spec = Spec(
            content_type="foo.Bar",
            attributes={
                "title": "Test Title",
                "image": BlobRef(
                    Key(type="url", value="https://example.com/image.png")
                ),
                "description": "A sample description",
                "call_to_action": ResourceRef(
                    Key(type="gen", value="call_to_action_123")
                ).pk,
                "child_object": {
                    "pk": ResourceRef(Key(type="gen", value="child_object_456")).pk,
                    "name": "Child Object Name",
                },
            },
        )

        assert spec == expected_spec

    def test_from_dict_with_lists(self):
        data = {
            "content_type": "foo.ListContainer",
            "attributes": {
                "images": [
                    "isekai-blob-ref:\\file:image1.jpg",
                    "isekai-blob-ref:\\file:image2.jpg",
                ],
                "references": [
                    "isekai-resource-ref:\\gen:ref1::pk",
                    "isekai-resource-ref:\\gen:ref2::pk",
                ],
                "mixed_list": [
                    "string_value",
                    42,
                    "isekai-resource-ref:\\gen:mixed_ref::pk",
                    {"nested_ref": "isekai-blob-ref:\\url:nested.png"},
                ],
            },
        }

        spec = Spec.from_dict(data)

        expected_spec = Spec(
            content_type="foo.ListContainer",
            attributes={
                "images": [
                    BlobRef(Key(type="file", value="image1.jpg")),
                    BlobRef(Key(type="file", value="image2.jpg")),
                ],
                "references": [
                    ResourceRef(Key(type="gen", value="ref1")).pk,
                    ResourceRef(Key(type="gen", value="ref2")).pk,
                ],
                "mixed_list": [
                    "string_value",
                    42,
                    ResourceRef(Key(type="gen", value="mixed_ref")).pk,
                    {"nested_ref": BlobRef(Key(type="url", value="nested.png"))},
                ],
            },
        )

        assert spec == expected_spec

    def test_from_dict_deeply_nested(self):
        data = {
            "content_type": "foo.DeepNested",
            "attributes": {
                "level1": {
                    "level2": {
                        "level3": {
                            "deep_ref": "isekai-resource-ref:\\deep:nested_value::pk",
                            "deep_list": [
                                "isekai-blob-ref:\\nested:deep_blob.png",
                                {
                                    "even_deeper": "isekai-resource-ref:\\deepest:bottom::pk"
                                },
                            ],
                        },
                    },
                },
            },
        }

        spec = Spec.from_dict(data)

        expected_spec = Spec(
            content_type="foo.DeepNested",
            attributes={
                "level1": {
                    "level2": {
                        "level3": {
                            "deep_ref": ResourceRef(
                                Key(type="deep", value="nested_value")
                            ).pk,
                            "deep_list": [
                                BlobRef(Key(type="nested", value="deep_blob.png")),
                                {
                                    "even_deeper": ResourceRef(
                                        Key(type="deepest", value="bottom")
                                    ).pk
                                },
                            ],
                        },
                    },
                },
            },
        )

        assert spec == expected_spec

    def test_from_dict_empty_attributes(self):
        data = {
            "content_type": "foo.Empty",
            "attributes": {},
        }

        spec = Spec.from_dict(data)

        expected_spec = Spec(
            content_type="foo.Empty",
            attributes={},
        )

        assert spec == expected_spec

    def test_from_dict_none_values(self):
        data = {
            "content_type": "foo.WithNone",
            "attributes": {
                "none_value": None,
                "ref_with_none": "isekai-resource-ref:\\gen:has_none::pk",
                "dict_with_none": {
                    "inner_none": None,
                    "inner_ref": "isekai-blob-ref:\\file:none_test.jpg",
                },
                "list_with_none": [None, "isekai-resource-ref:\\gen:in_list::pk"],
            },
        }

        spec = Spec.from_dict(data)

        expected_spec = Spec(
            content_type="foo.WithNone",
            attributes={
                "none_value": None,
                "ref_with_none": ResourceRef(Key(type="gen", value="has_none")).pk,
                "dict_with_none": {
                    "inner_none": None,
                    "inner_ref": BlobRef(Key(type="file", value="none_test.jpg")),
                },
                "list_with_none": [
                    None,
                    ResourceRef(Key(type="gen", value="in_list")).pk,
                ],
            },
        )

        assert spec == expected_spec

    def test_from_dict_invalid_ref_string(self):
        data = {
            "content_type": "foo.Invalid",
            "attributes": {
                "bad_ref": "invalid-ref-string",
            },
        }

        spec = Spec.from_dict(data)

        # Should not parse invalid ref strings, just keep them as strings
        expected_spec = Spec(
            content_type="foo.Invalid",
            attributes={
                "bad_ref": "invalid-ref-string",
            },
        )

        assert spec == expected_spec

    def test_roundtrip_to_dict_from_dict(self):
        original_spec = Spec(
            content_type="foo.Roundtrip",
            attributes={
                "title": "Roundtrip Test",
                "image": BlobRef(Key(type="url", value="https://example.com/test.jpg")),
                "refs": [
                    ResourceRef(Key(type="gen", value="ref1")).pk,
                    ResourceRef(Key(type="gen", value="ref2")).pk,
                ],
                "nested": {
                    "deep_ref": ResourceRef(Key(type="deep", value="nested")).pk,
                    "values": [
                        1,
                        2,
                        None,
                        BlobRef(Key(type="file", value="nested.png")),
                    ],
                },
            },
        )

        # Convert to dict and back
        dict_data = original_spec.to_dict()
        reconstructed_spec = Spec.from_dict(dict_data)

        assert reconstructed_spec == original_spec

    def test_find_refs(self):
        spec = Spec(
            content_type="foo.WithRefs",
            attributes={
                "title": "Test Title",
                "image": BlobRef(
                    Key(type="url", value="https://example.com/image.png")
                ),
                "call_to_action": ResourceRef(
                    Key(type="gen", value="call_to_action_123")
                ).pk,
                "child_object": {
                    "pk": ResourceRef(Key(type="gen", value="child_object_456")).pk,
                    "image": BlobRef(Key(type="file", value="child.jpg")),
                    "name": "Child Object Name",
                },
                "refs_list": [
                    ResourceRef(Key(type="gen", value="ref1")).pk,
                    BlobRef(Key(type="file", value="list_blob.jpg")),
                    "string_value",
                ],
                "duplicate_ref": ResourceRef(
                    Key(type="gen", value="call_to_action_123")
                ).pk,  # Duplicate
                "nested": {
                    "deep": {
                        "ref": ResourceRef(Key(type="gen", value="deep_ref")).pk,
                        "blob": BlobRef(Key(type="url", value="deep.png")),
                    }
                },
            },
        )

        refs = spec.find_refs()

        # Should contain all unique refs without duplicates
        expected_refs = [
            BlobRef(Key(type="url", value="https://example.com/image.png")),
            ResourceRef(Key(type="gen", value="call_to_action_123")).pk,
            ResourceRef(Key(type="gen", value="child_object_456")).pk,
            BlobRef(Key(type="file", value="child.jpg")),
            ResourceRef(Key(type="gen", value="ref1")).pk,
            BlobRef(Key(type="file", value="list_blob.jpg")),
            ResourceRef(Key(type="gen", value="deep_ref")).pk,
            BlobRef(Key(type="url", value="deep.png")),
        ]

        assert len(refs) == len(expected_refs)
        for expected_ref in expected_refs:
            assert expected_ref in refs

    def test_find_refs_no_refs(self):
        spec = Spec(
            content_type="foo.NoRefs",
            attributes={
                "title": "Test Title",
                "count": 42,
                "nested": {
                    "value": "string",
                    "list": [1, 2, "three"],
                },
            },
        )

        refs = spec.find_refs()
        assert refs == []

    def test_find_refs_with_single_string_ref(self):
        """Test finding a single ResourceRef embedded in a string."""
        author_key = Key(type="url", value="https://example.com/author/1")
        spec = Spec(
            content_type="testapp.Article",
            attributes={
                "title": f"Article by {ref(ResourceRef(author_key).name)}",
            },
        )

        refs = spec.find_refs()

        # Should find the ResourceRef embedded in the string
        expected_ref = ResourceRef(author_key).name
        assert len(refs) == 1
        assert expected_ref in refs

    def test_find_refs_with_multiple_string_refs(self):
        """Test finding multiple refs embedded in a single string."""
        author_key = Key(type="url", value="https://example.com/author/1")
        category_key = Key(type="url", value="https://example.com/category/tech")
        spec = Spec(
            content_type="testapp.Article",
            attributes={
                "description": f"Written by {ref(ResourceRef(author_key).name)} in {ref(ResourceRef(category_key).name)}",
            },
        )

        refs = spec.find_refs()

        # Should find both ResourceRefs embedded in the string
        assert len(refs) == 2
        assert ResourceRef(author_key).name in refs
        assert ResourceRef(category_key).name in refs

    def test_find_refs_with_blob_ref_in_string(self):
        """Test finding BlobRef embedded in a string."""
        image_key = Key(type="url", value="https://example.com/avatar.jpg")
        spec = Spec(
            content_type="testapp.Author",
            attributes={
                "bio": f"Profile picture: {ref(BlobRef(image_key))}",
            },
        )

        refs = spec.find_refs()

        # Should find the BlobRef embedded in the string
        expected_ref = BlobRef(image_key)
        assert len(refs) == 1
        assert expected_ref in refs

    def test_find_refs_ignores_model_ref_in_string(self):
        """Test that ModelRef in string is ignored (not a dependency)."""
        spec = Spec(
            content_type="testapp.Article",
            attributes={
                "author": ModelRef("testapp.Author", pk=42).pk,
                "description": f"By {ref(ModelRef('testapp.Author', pk=42).name)}",
            },
        )

        refs = spec.find_refs()

        # Should not find any refs (ModelRef is not a dependency)
        assert len(refs) == 0

    def test_find_refs_with_nested_string_refs(self):
        """Test finding refs in strings within nested structures."""
        author_key = Key(type="url", value="https://example.com/author/1")
        image_key = Key(type="url", value="https://example.com/image.jpg")
        spec = Spec(
            content_type="testapp.Article",
            attributes={
                "metadata": {
                    "credit": f"Photo by {ref(ResourceRef(author_key).name)}",
                    "info": {
                        "caption": f"See image at {ref(BlobRef(image_key))}",
                    },
                },
            },
        )

        refs = spec.find_refs()

        # Should find both refs in nested strings
        assert len(refs) == 2
        assert ResourceRef(author_key).name in refs
        assert BlobRef(image_key) in refs

    def test_find_refs_mixed_direct_and_string_refs(self):
        """Test finding both direct refs and refs embedded in strings."""
        author_key = Key(type="url", value="https://example.com/author/1")
        image_key = Key(type="url", value="https://example.com/image.jpg")
        category_key = Key(type="url", value="https://example.com/category/tech")

        spec = Spec(
            content_type="testapp.Article",
            attributes={
                "featured_image": BlobRef(image_key),  # Direct BlobRef
                "author": ResourceRef(author_key).pk,  # Direct ResourceRef
                "description": f"Category: {ref(ResourceRef(category_key).name)}",  # String ref
            },
        )

        refs = spec.find_refs()

        # Should find all three refs (2 direct + 1 in string)
        assert len(refs) == 3
        assert BlobRef(image_key) in refs
        assert ResourceRef(author_key).pk in refs
        assert ResourceRef(category_key).name in refs

from isekai.types import BlobRef, Key, ModelRef, PkRef, Spec
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
    def test_pk_ref(self):
        key = Key(type="test", value="123")

        # Key to PkRef
        ref = PkRef(key)
        assert str(ref) == "isekai-pk-ref:\\test:123"

        # PkRef to Key
        ref = PkRef.from_string("isekai-pk-ref:\\test:123")
        assert ref.key == key

    def test_model_ref(self):
        key = Key(type="test", value="456")

        # Key to ModelRef
        ref = ModelRef(key)
        assert str(ref) == "isekai-model-ref:\\test:456"

        # ModelRef to Key
        ref = ModelRef.from_string("isekai-model-ref:\\test:456")
        assert ref.key == key

    def test_ref_invalid_string(self):
        # Invalid format should raise ValueError
        with pytest.raises(ValueError):
            PkRef.from_string("invalid-string")

        # Invalid prefix should raise ValueError
        with pytest.raises(ValueError):
            PkRef.from_string("ref:\\test:123")

        with pytest.raises(ValueError):
            ModelRef.from_string("invalid-string")

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
                "call_to_action": PkRef(Key(type="gen", value="call_to_action_123")),
                "child_object": {
                    "pk": PkRef(Key(type="gen", value="child_object_456")),
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
                "call_to_action": "isekai-pk-ref:\\gen:call_to_action_123",
                "child_object": {
                    "pk": "isekai-pk-ref:\\gen:child_object_456",
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
                    PkRef(Key(type="gen", value="ref1")),
                    PkRef(Key(type="gen", value="ref2")),
                ],
                "mixed_list": [
                    "string_value",
                    42,
                    PkRef(Key(type="gen", value="mixed_ref")),
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
                    "isekai-pk-ref:\\gen:ref1",
                    "isekai-pk-ref:\\gen:ref2",
                ],
                "mixed_list": [
                    "string_value",
                    42,
                    "isekai-pk-ref:\\gen:mixed_ref",
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
                    PkRef(Key(type="gen", value="tuple_ref1")),
                    BlobRef(Key(type="file", value="tuple_blob.jpg")),
                    "tuple_string",
                ),
            },
        )

        expected_dict = {
            "content_type": "foo.TupleContainer",
            "attributes": {
                "tuple_refs": [
                    "isekai-pk-ref:\\gen:tuple_ref1",
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
                            "deep_ref": PkRef(Key(type="deep", value="nested_value")),
                            "deep_list": [
                                BlobRef(Key(type="nested", value="deep_blob.png")),
                                {
                                    "even_deeper": PkRef(
                                        Key(type="deepest", value="bottom")
                                    )
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
                            "deep_ref": "isekai-pk-ref:\\deep:nested_value",
                            "deep_list": [
                                "isekai-blob-ref:\\nested:deep_blob.png",
                                {"even_deeper": "isekai-pk-ref:\\deepest:bottom"},
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
                "ref_with_none": PkRef(Key(type="gen", value="has_none")),
                "dict_with_none": {
                    "inner_none": None,
                    "inner_ref": BlobRef(Key(type="file", value="none_test.jpg")),
                },
                "list_with_none": [None, PkRef(Key(type="gen", value="in_list"))],
            },
        )

        expected_dict = {
            "content_type": "foo.WithNone",
            "attributes": {
                "none_value": None,
                "ref_with_none": "isekai-pk-ref:\\gen:has_none",
                "dict_with_none": {
                    "inner_none": None,
                    "inner_ref": "isekai-blob-ref:\\file:none_test.jpg",
                },
                "list_with_none": [None, "isekai-pk-ref:\\gen:in_list"],
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
                "call_to_action": "isekai-pk-ref:\\gen:call_to_action_123",
                "child_object": {
                    "pk": "isekai-pk-ref:\\gen:child_object_456",
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
                "call_to_action": PkRef(Key(type="gen", value="call_to_action_123")),
                "child_object": {
                    "pk": PkRef(Key(type="gen", value="child_object_456")),
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
                    "isekai-pk-ref:\\gen:ref1",
                    "isekai-pk-ref:\\gen:ref2",
                ],
                "mixed_list": [
                    "string_value",
                    42,
                    "isekai-pk-ref:\\gen:mixed_ref",
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
                    PkRef(Key(type="gen", value="ref1")),
                    PkRef(Key(type="gen", value="ref2")),
                ],
                "mixed_list": [
                    "string_value",
                    42,
                    PkRef(Key(type="gen", value="mixed_ref")),
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
                            "deep_ref": "isekai-pk-ref:\\deep:nested_value",
                            "deep_list": [
                                "isekai-blob-ref:\\nested:deep_blob.png",
                                {"even_deeper": "isekai-pk-ref:\\deepest:bottom"},
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
                            "deep_ref": PkRef(Key(type="deep", value="nested_value")),
                            "deep_list": [
                                BlobRef(Key(type="nested", value="deep_blob.png")),
                                {
                                    "even_deeper": PkRef(
                                        Key(type="deepest", value="bottom")
                                    )
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
                "ref_with_none": "isekai-pk-ref:\\gen:has_none",
                "dict_with_none": {
                    "inner_none": None,
                    "inner_ref": "isekai-blob-ref:\\file:none_test.jpg",
                },
                "list_with_none": [None, "isekai-pk-ref:\\gen:in_list"],
            },
        }

        spec = Spec.from_dict(data)

        expected_spec = Spec(
            content_type="foo.WithNone",
            attributes={
                "none_value": None,
                "ref_with_none": PkRef(Key(type="gen", value="has_none")),
                "dict_with_none": {
                    "inner_none": None,
                    "inner_ref": BlobRef(Key(type="file", value="none_test.jpg")),
                },
                "list_with_none": [None, PkRef(Key(type="gen", value="in_list"))],
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
                    PkRef(Key(type="gen", value="ref1")),
                    PkRef(Key(type="gen", value="ref2")),
                ],
                "nested": {
                    "deep_ref": PkRef(Key(type="deep", value="nested")),
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
                "call_to_action": PkRef(Key(type="gen", value="call_to_action_123")),
                "child_object": {
                    "pk": PkRef(Key(type="gen", value="child_object_456")),
                    "image": BlobRef(Key(type="file", value="child.jpg")),
                    "name": "Child Object Name",
                },
                "refs_list": [
                    PkRef(Key(type="gen", value="ref1")),
                    BlobRef(Key(type="file", value="list_blob.jpg")),
                    "string_value",
                ],
                "duplicate_ref": PkRef(
                    Key(type="gen", value="call_to_action_123")
                ),  # Duplicate
                "nested": {
                    "deep": {
                        "ref": PkRef(Key(type="gen", value="deep_ref")),
                        "blob": BlobRef(Key(type="url", value="deep.png")),
                    }
                },
            },
        )

        refs = spec.find_refs()

        # Should contain all unique refs without duplicates
        expected_refs = [
            BlobRef(Key(type="url", value="https://example.com/image.png")),
            PkRef(Key(type="gen", value="call_to_action_123")),
            PkRef(Key(type="gen", value="child_object_456")),
            BlobRef(Key(type="file", value="child.jpg")),
            PkRef(Key(type="gen", value="ref1")),
            BlobRef(Key(type="file", value="list_blob.jpg")),
            PkRef(Key(type="gen", value="deep_ref")),
            BlobRef(Key(type="url", value="deep.png")),
        ]

        assert len(refs) == len(expected_refs)
        for ref in expected_refs:
            assert ref in refs

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

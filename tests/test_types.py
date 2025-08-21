from isekai.types import BlobRef, Key, Ref
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
    def test_ref(self):
        key = Key(type="test", value="123")

        # Key to Ref
        ref = Ref(key)
        assert str(ref) == "isekai-ref:\\test:123"

        # Ref to Key
        ref = Ref.from_string("isekai-ref:\\test:123")
        assert ref.key == key

    def test_ref_invalid_string(self):
        # Invalid format should raise ValueError
        with pytest.raises(ValueError):
            Ref.from_string("invalid-string")

        # Invalid prefix should raise ValueError
        with pytest.raises(ValueError):
            Ref.from_string("ref:\\test:123")

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

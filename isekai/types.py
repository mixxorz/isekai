import io
import os
from collections.abc import Mapping
from dataclasses import dataclass
from pathlib import Path
from typing import IO, TYPE_CHECKING, Any, ClassVar, Literal, Protocol, overload
from urllib.parse import parse_qs, unquote, urlencode

if TYPE_CHECKING:
    from django.db.models import FieldFile, Model


@dataclass(frozen=True, slots=True)
class Key:
    """
    Represents a resource key.
    """

    type: str
    value: str

    @classmethod
    def from_string(cls, key: str) -> "Key":
        """
        Parses a string into a Key object.
        """
        try:
            key, value = key.split(":", 1)

            if value == "":
                raise ValueError("Key must have a value.")

        except ValueError as err:
            raise ValueError(f"Invalid key format: {key}.") from err

        return cls(type=key, value=value)

    def __str__(self) -> str:
        """
        Returns the string representation of the Key.
        """
        return f"{self.type}:{self.value}"


@dataclass(frozen=True, slots=True)
class SeededResource:
    key: Key
    metadata: Mapping[str, Any]


@dataclass(frozen=True, slots=True)
class TextResource:
    mime_type: str
    text: str
    metadata: Mapping[str, Any]


class FileProxy(Protocol):
    @property
    def name(self) -> str: ...
    def open(self) -> IO[bytes]: ...


@dataclass(frozen=True)
class PathFileProxy:
    path: Path

    @property
    def name(self) -> str:
        return self.path.name

    def open(self) -> IO[bytes]:
        return self.path.open("rb")


@dataclass(frozen=True)
class FieldFileProxy:
    ff: "FieldFile"

    @property
    def name(self) -> str:
        return os.path.basename(self.ff.name)

    def open(self) -> IO[bytes]:
        return self.ff.storage.open(self.ff.name, mode="rb")


@dataclass(frozen=True)
class InMemoryFileProxy:
    content: bytes

    @property
    def name(self):
        return "in_memory_file"

    def open(self) -> IO[bytes]:
        return io.BytesIO(self.content)


@dataclass(frozen=True, slots=True)
class BlobResource:
    mime_type: str
    filename: str
    file_ref: FileProxy
    metadata: Mapping[str, Any]


@dataclass(frozen=True, slots=True)
class MinedResource:
    key: Key
    metadata: Mapping[str, Any]


@dataclass(frozen=True, slots=True)
class Spec:
    content_type: str
    attributes: dict[str, Any]

    def to_dict(self):
        def serialize_value(value):
            if isinstance(value, BaseRef | ResourceRef | ModelRef):
                return str(value)
            elif isinstance(value, dict):
                return {k: serialize_value(v) for k, v in value.items()}
            elif isinstance(value, list | tuple):
                return [serialize_value(v) for v in value]
            return value

        return {
            "content_type": self.content_type,
            "attributes": {
                key: serialize_value(value) for key, value in self.attributes.items()
            },
        }

    @classmethod
    def from_dict(cls, data):
        def deserialize_value(value):
            if isinstance(value, str):
                # Try to parse as various ref types
                try:
                    if value.startswith("isekai-resource-ref:\\"):
                        return ResourceRef.from_string(value)
                    elif value.startswith("isekai-blob-ref:\\"):
                        return BlobRef.from_string(value)
                    elif value.startswith("isekai-model-ref:\\"):
                        return ModelRef.from_string(value)
                except ValueError:
                    pass
                # If parsing fails or doesn't match patterns, return as string
                return value
            elif isinstance(value, dict):
                return {k: deserialize_value(v) for k, v in value.items()}
            elif isinstance(value, list | tuple):
                return [deserialize_value(v) for v in value]
            return value

        return cls(
            content_type=data["content_type"],
            attributes={
                key: deserialize_value(value)
                for key, value in data["attributes"].items()
            },
        )

    def find_refs(self) -> list["BaseRef | ResourceRef | ModelRef"]:
        """
        Find all Refs in the attributes dict.

        Only BlobRef and ResourceRef create resource dependencies.
        ModelRef doesn't create dependencies since it references existing DB objects directly.
        """
        refs = []
        seen = set()

        def collect_refs(value):
            if isinstance(value, BaseRef | ResourceRef):
                # Only collect BlobRef and ResourceRef, not ModelRef
                ref_str = str(value)
                if ref_str not in seen:
                    seen.add(ref_str)
                    refs.append(value)
            elif isinstance(value, dict):
                for v in value.values():
                    collect_refs(v)
            elif isinstance(value, list | tuple):
                for item in value:
                    collect_refs(item)

        collect_refs(self.attributes)
        return refs


@dataclass(frozen=True, slots=True)
class BaseRef:
    """
    Base class for all reference types.
    """

    key: Key
    _prefix: ClassVar[str]  # Must be overridden in subclasses

    @classmethod
    def from_string(cls, refstr: str):
        """
        Parses a string into a reference object.
        """
        if not refstr.startswith(cls._prefix):
            raise ValueError(f"Invalid ref: {refstr}")

        key = Key.from_string(refstr.removeprefix(cls._prefix))
        return cls(key=key)

    def __str__(self) -> str:
        """
        Returns the string representation of the reference.
        """
        return f"{self._prefix}{self.key}"


class ModelRef:
    """
    Represents a reference to an existing database model using content_type and lookup kwargs.

    Supports lazy attribute chaining: ModelRef("app.Model", pk=42).group.name

    Will fetch the model from the database and resolve to the instance (or attribute value) during Load.
    """

    _prefix: ClassVar[str] = "isekai-model-ref:\\"

    def __init__(
        self, content_type: str, attr_path: tuple[str, ...] = (), **lookup_kwargs
    ):
        object.__setattr__(self, "ref_content_type", content_type)
        object.__setattr__(self, "ref_lookup_kwargs", lookup_kwargs)
        object.__setattr__(self, "ref_attr_path", attr_path)

    def __getattr__(self, name: str) -> "ModelRef":
        """
        Capture attribute access and return a new ModelRef with extended attr_path.
        """
        # Return new ModelRef with extended attribute path
        new_ref = ModelRef.__new__(ModelRef)
        object.__setattr__(new_ref, "ref_content_type", self.ref_content_type)
        object.__setattr__(new_ref, "ref_lookup_kwargs", self.ref_lookup_kwargs)
        object.__setattr__(new_ref, "ref_attr_path", self.ref_attr_path + (name,))
        return new_ref

    def __eq__(self, other):
        if not isinstance(other, ModelRef):
            return False
        return (
            self.ref_content_type == other.ref_content_type
            and self.ref_lookup_kwargs == other.ref_lookup_kwargs
            and self.ref_attr_path == other.ref_attr_path
        )

    def __hash__(self):
        return hash(
            (
                self.ref_content_type,
                tuple(sorted(self.ref_lookup_kwargs.items())),
                self.ref_attr_path,
            )
        )

    @classmethod
    def from_string(cls, refstr: str) -> "ModelRef":
        """
        Parses a string into a ModelRef object.
        Format: "isekai-model-ref:\\app.Model?pk=42&slug=foo::attr1.attr2"
        """
        if not refstr.startswith(cls._prefix):
            raise ValueError(f"Invalid ref: {refstr}")

        # Remove prefix
        rest = refstr.removeprefix(cls._prefix)

        # Check if there's an attribute path
        if "::" in rest:
            query_part, attr_str = rest.split("::", 1)
            attr_path = tuple(attr_str.split("."))
        else:
            query_part = rest
            attr_path = ()

        # Split content_type and query string
        if "?" in query_part:
            content_type, query_string = query_part.split("?", 1)
            # Parse query string - parse_qs returns lists, we want single values
            parsed = parse_qs(query_string)
            lookup_kwargs = {k: unquote(v[0]) for k, v in parsed.items()}
        else:
            raise ValueError(
                f"Invalid ModelRef format (missing query params): {refstr}"
            )

        return cls(content_type=content_type, attr_path=attr_path, **lookup_kwargs)

    def __str__(self) -> str:
        """
        Returns the string representation of the ModelRef.
        """
        # Convert lookup_kwargs to query string
        query_string = urlencode(self.ref_lookup_kwargs)
        base = f"{self._prefix}{self.ref_content_type}?{query_string}"

        if self.ref_attr_path:
            return f"{base}::{'.'.join(self.ref_attr_path)}"
        return base


@dataclass(frozen=True, slots=True)
class BlobRef(BaseRef):
    """
    Represents a reference to a blob resource using a Key.

    Will be replaced by the resource's blob data during Load.
    """

    _prefix = "isekai-blob-ref:\\"


class ResourceRef:
    """
    Represents a reference to a resource using a Key with optional attribute access.

    Supports lazy attribute chaining: ResourceRef(key).group.name

    Will be replaced by the resource's model instance (or attribute value) during Load.
    """

    _prefix: ClassVar[str] = "isekai-resource-ref:\\"

    def __init__(self, key: Key, attr_path: tuple[str, ...] = ()):
        object.__setattr__(self, "key", key)
        object.__setattr__(self, "ref_attr_path", attr_path)

    def __getattr__(self, name: str) -> "ResourceRef":
        """
        Capture attribute access and return a new ResourceRef with extended attr_path.
        """
        # Return new ResourceRef with extended attribute path
        new_ref = ResourceRef.__new__(ResourceRef)
        object.__setattr__(new_ref, "key", self.key)
        object.__setattr__(new_ref, "ref_attr_path", self.ref_attr_path + (name,))
        return new_ref

    def __eq__(self, other):
        if not isinstance(other, ResourceRef):
            return False
        return self.key == other.key and self.ref_attr_path == other.ref_attr_path

    def __hash__(self):
        return hash((self.key, self.ref_attr_path))

    @classmethod
    def from_string(cls, refstr: str) -> "ResourceRef":
        """
        Parses a string into a ResourceRef object.
        Format: "isekai-resource-ref:\\type:value" or "isekai-resource-ref:\\type:value::attr1.attr2"
        """
        if not refstr.startswith(cls._prefix):
            raise ValueError(f"Invalid ref: {refstr}")

        # Remove prefix
        rest = refstr.removeprefix(cls._prefix)

        # Check if there's an attribute path
        if "::" in rest:
            key_str, attr_str = rest.split("::", 1)
            attr_path = tuple(attr_str.split("."))
        else:
            key_str = rest
            attr_path = ()

        key = Key.from_string(key_str)
        return cls(key=key, attr_path=attr_path)

    def __str__(self) -> str:
        """
        Returns the string representation of the ResourceRef.
        """
        base = f"{self._prefix}{self.key}"
        if self.ref_attr_path:
            return f"{base}::{'.'.join(self.ref_attr_path)}"
        return base


class Resolver(Protocol):
    """
    A resolver function that takes a ref and returns the appropriate value:
    - BlobRef -> FileProxy
    - ResourceRef -> model instance or attribute value
    - ModelRef -> model instance or attribute value
    """

    @overload
    def __call__(self, ref: BlobRef) -> FileProxy: ...
    @overload
    def __call__(self, ref: ResourceRef) -> "Model | int | str": ...
    @overload
    def __call__(self, ref: ModelRef) -> "Model": ...


@dataclass
class OperationResult:
    result: Literal["success", "partial_success", "failure"]
    messages: list[str]
    metadata: dict[str, Any]


class Operation(Protocol):
    def __call__(self) -> OperationResult: ...


# Exceptions
class TransitionError(Exception):
    pass


class ExtractError(Exception):
    pass


class TransformError(Exception):
    pass

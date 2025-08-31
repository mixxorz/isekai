import io
import os
from collections.abc import Mapping
from dataclasses import dataclass
from pathlib import Path
from typing import IO, TYPE_CHECKING, Any, ClassVar, Literal, Protocol, overload

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
            if isinstance(value, BaseRef):
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
                # Try to parse as BlobRef first, then ModelRef, then PkRef
                try:
                    if value.startswith("isekai-blob-ref:\\"):
                        return BlobRef.from_string(value)
                    elif value.startswith("isekai-model-ref:\\"):
                        return ModelRef.from_string(value)
                    elif value.startswith("isekai-pk-ref:\\"):
                        return PkRef.from_string(value)
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

    def find_refs(self) -> list["BaseRef"]:
        """
        Find all Refs in the attributes dict.
        """
        refs = []
        seen = set()

        def collect_refs(value):
            if isinstance(value, BaseRef):
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


@dataclass(frozen=True, slots=True)
class PkRef(BaseRef):
    """
    Represents a reference to a resource using a Key.

    Will be replaced by the resource's final primary key during Load.
    """

    _prefix = "isekai-pk-ref:\\"


@dataclass(frozen=True, slots=True)
class ModelRef(BaseRef):
    """
    Represents a reference to a resource using a Key.

    Will be replaced by the resource's model instance during Load.
    """

    _prefix = "isekai-model-ref:\\"


@dataclass(frozen=True, slots=True)
class BlobRef(BaseRef):
    """
    Represents a reference to a blob resource using a Key.

    Will be replaced by the resource's blob data during Load.
    """

    _prefix = "isekai-blob-ref:\\"


class Resolver(Protocol):
    """
    A resolver function that takes a ref and returns the appropriate value:
    - BlobRef -> FileProxy
    - PkRef -> database PK (int | str)
    - ModelRef -> model instance
    """

    @overload
    def __call__(self, ref: BlobRef) -> FileProxy: ...
    @overload
    def __call__(self, ref: PkRef) -> int | str: ...
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

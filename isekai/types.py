import io
from collections.abc import Mapping
from dataclasses import dataclass
from pathlib import Path
from typing import IO, TYPE_CHECKING, Any, Protocol

if TYPE_CHECKING:
    from django.db.models import FieldFile


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


class FileRef(Protocol):
    def open(self) -> IO[bytes]: ...


@dataclass(frozen=True)
class PathFileRef:
    path: Path

    def open(self) -> IO[bytes]:
        return self.path.open("rb")


@dataclass(frozen=True)
class FieldFileRef:
    ff: "FieldFile"

    def open(self) -> IO[bytes]:
        return self.ff.storage.open(self.ff.name, mode="rb")


@dataclass(frozen=True)
class InMemoryFileRef:
    content: bytes

    def open(self) -> IO[bytes]:
        return io.BytesIO(self.content)


@dataclass(frozen=True, slots=True)
class BlobResource:
    mime_type: str
    filename: str
    file_ref: FileRef
    metadata: Mapping[str, Any]


@dataclass(frozen=True, slots=True)
class MinedResource:
    key: Key
    metadata: Mapping[str, Any]


@dataclass(frozen=True, slots=True)
class Spec:
    content_type: str
    attributes: Mapping[str, Any]


@dataclass(frozen=True, slots=True)
class Ref:
    """
    Represents a reference to a resource using a Key.

    Will be replaced by the resource's final primary key during Load.
    """

    key: Key

    _prefix = "isekai-ref:\\"

    @classmethod
    def from_string(cls, refstr: str) -> "Ref":
        """
        Parses a string into a Ref object.
        """
        if not refstr.startswith(cls._prefix):
            raise ValueError(f"Invalid ref: {refstr}")

        key = Key.from_string(refstr.removeprefix(cls._prefix))
        return cls(key=key)

    def __str__(self) -> str:
        """
        Returns the string representation of the Ref.
        """
        return f"{self._prefix}{self.key}"


@dataclass(frozen=True, slots=True)
class BlobRef(Ref):
    """
    Represents a reference to a blob resource using a Key.

    Will be replaced by the resource's blob data during Load.
    """

    _prefix = "isekai-blob-ref:\\"


# Exceptions
class TransitionError(Exception):
    pass


class ExtractionError(Exception):
    pass

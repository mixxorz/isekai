from collections.abc import Mapping
from dataclasses import dataclass
from pathlib import Path
from typing import IO, TYPE_CHECKING, Any

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
        key, value = key.split(":", 1)
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


@dataclass(frozen=True, slots=True)
class BlobResource:
    mime_type: str
    filename: str
    file_ref: PathFileRef | FieldFileRef
    metadata: Mapping[str, Any]


@dataclass(frozen=True, slots=True)
class MinedResource:
    key: Key
    metadata: Mapping[str, Any]


# Exceptions
class TransitionError(Exception):
    pass


class ExtractionError(Exception):
    pass

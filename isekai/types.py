from collections.abc import Mapping
from dataclasses import dataclass
from pathlib import Path
from typing import Any


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


@dataclass(frozen=True, slots=True)
class BlobResource:
    mime_type: str
    filename: str
    path: Path
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

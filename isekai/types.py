from dataclasses import dataclass, field
from typing import Literal


@dataclass
class BinaryData:
    """
    Represents binary data.
    """

    filename: str
    data: bytes


@dataclass
class ResourceData:
    """
    Represents the data for a resource.
    """

    mime_type: str
    data_type: Literal["text", "blob"]
    data: str | BinaryData
    metadata: dict = field(default_factory=dict)


class TransitionError(Exception):
    pass


class ExtractionError(Exception):
    pass

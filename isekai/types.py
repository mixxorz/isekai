from dataclasses import dataclass
from typing import Literal


@dataclass
class ResourceData:
    """
    Represents the data for a resource.
    """

    mime_type: str
    data_type: Literal["text", "blob"]
    data: str | bytes


class TransitionError(Exception):
    pass


class ExtractionError(Exception):
    pass

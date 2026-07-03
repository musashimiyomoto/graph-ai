"""Node-related enums."""

from enum import StrEnum, auto


class NodeType(StrEnum):
    """Supported node types in a workflow graph."""

    INPUT = auto()
    LLM = auto()
    WEB_SEARCH = auto()
    TEMPLATE = auto()
    HTTP_REQUEST = auto()
    OUTPUT = auto()


class HttpMethod(StrEnum):
    """HTTP methods supported by the HTTP request node."""

    GET = auto()
    POST = auto()
    PUT = auto()
    PATCH = auto()
    DELETE = auto()

    @property
    def allows_body(self) -> bool:
        """Whether this method sends a request body."""
        return self in {HttpMethod.POST, HttpMethod.PUT, HttpMethod.PATCH}


class PortType(StrEnum):
    """Data type carried by a node input/output port."""

    TEXT = auto()
    JSON = auto()
    FILE = auto()
    LIST = auto()


class InputNodeFormat(StrEnum):
    """Supported input node formats."""

    TXT = auto()


class OutputNodeFormat(StrEnum):
    """Supported output node formats."""

    TXT = auto()

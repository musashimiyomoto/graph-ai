"""Node-related enums."""

from enum import StrEnum, auto


class NodeType(StrEnum):
    """Supported node types in a workflow graph."""

    INPUT = auto()
    LLM = auto()
    WEB_SEARCH = auto()
    TEMPLATE = auto()
    HTTP_REQUEST = auto()
    CONDITION = auto()
    CODE_TRANSFORM = auto()
    VECTOR_INGEST = auto()
    VECTOR_SEARCH = auto()
    LOOP = auto()
    LOOP_INPUT = auto()
    LOOP_OUTPUT = auto()
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
    TELEGRAM = auto()
    SCHEDULE = auto()


class OutputNodeFormat(StrEnum):
    """Supported output node formats."""

    TXT = auto()
    TELEGRAM = auto()


class ConditionType(StrEnum):
    """Supported evaluation modes for the condition/router node."""

    CONTAINS = auto()
    EQUALS = auto()
    REGEX = auto()
    NOT_EMPTY = auto()

    @property
    def needs_value(self) -> bool:
        """Whether this condition type requires a comparison value."""
        return self is not ConditionType.NOT_EMPTY


class ConditionBranch(StrEnum):
    """Output handles of the condition/router node."""

    TRUE = "true"
    FALSE = "false"


class LoopMode(StrEnum):
    """How a loop node determines when to stop iterating."""

    LIST = auto()
    CONDITION = auto()

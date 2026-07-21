"""Node-related enums."""

from enum import StrEnum, auto


class NodeType(StrEnum):
    """Supported node types in a workflow graph."""

    INPUT = auto()
    LLM = auto()
    TRANSLATE = auto()
    DELAY = auto()
    WEB_SEARCH = auto()
    TEMPLATE = auto()
    HTTP_REQUEST = auto()
    CONDITION = auto()
    SWITCH = auto()
    MCP_TOOL = auto()
    CODE_TRANSFORM = auto()
    VECTOR_INGEST = auto()
    VECTOR_SEARCH = auto()
    TABLE = auto()
    CALL_WORKFLOW = auto()
    APPROVAL = auto()
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


class TableSource(StrEnum):
    """Sources supported by the Table node."""

    GOOGLE_SHEETS = auto()
    CSV = auto()
    POSTGRES = auto()


class PortType(StrEnum):
    """Data type carried by a node input/output port."""

    TEXT = auto()
    JSON = auto()
    FILE = auto()
    LIST = auto()
    IMAGE = auto()
    AUDIO = auto()
    VIDEO = auto()


class PortCoercion(StrEnum):
    """Explicit value conversion stored on a workflow edge."""

    TEXT_TO_JSON = auto()
    JSON_TO_TEXT = auto()
    TEXT_TO_LIST = auto()
    LIST_TO_TEXT = auto()
    JSON_TO_LIST = auto()
    LIST_TO_JSON = auto()
    IMAGE_TO_FILE = auto()
    AUDIO_TO_FILE = auto()
    VIDEO_TO_FILE = auto()


class InputNodeFormat(StrEnum):
    """Supported input node formats."""

    TXT = auto()
    TELEGRAM = auto()
    SCHEDULE = auto()
    EMAIL = auto()
    WEBHOOK = auto()
    WEB_CHAT = auto()


class OutputNodeFormat(StrEnum):
    """Supported output node formats."""

    TXT = auto()
    TELEGRAM = auto()
    EMAIL = auto()
    WEBHOOK = auto()
    WEB_CHAT = auto()


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


class DelayMode(StrEnum):
    """How a Delay node determines its wake-up time."""

    DURATION = auto()
    UNTIL = auto()


class DelayUnit(StrEnum):
    """Units accepted by duration-based Delay nodes."""

    SECONDS = auto()
    MINUTES = auto()
    HOURS = auto()
    DAYS = auto()

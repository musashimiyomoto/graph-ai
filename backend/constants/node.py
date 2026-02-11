"""Node-related constants."""

from enums import ValidatorType

MIN_LENGTH_KEY = ValidatorType.MIN_LENGTH.value
SELECT_KEY = ValidatorType.SELECT.value
GE_KEY = ValidatorType.GE.value
LE_KEY = ValidatorType.LE.value

DEFAULT_TEXT_FORMAT = "txt"
TEXT_FORMAT_OPTIONS: tuple[str, ...] = (DEFAULT_TEXT_FORMAT,)

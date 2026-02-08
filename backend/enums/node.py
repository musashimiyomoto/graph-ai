"""Node-related enums."""

from enum import Enum, StrEnum, auto

from enums.validator import ValidatorType


class NodeType(StrEnum):
    """Supported node types in a workflow graph."""

    INPUT = auto()
    LLM = auto()
    OUTPUT = auto()


class InputNodeFormat(StrEnum):
    """Supported input node formats."""

    TXT = auto()


class OutputNodeFormat(StrEnum):
    """Supported output node formats."""

    TXT = auto()


class NodeDataSpec(Enum):
    """Node data specs keyed by node type."""

    _V = ValidatorType

    INPUT = (
        {"name": "label", "validators": {_V.MIN_LENGTH: 1}},
        {"name": "format", "validators": {_V.SELECT: list(InputNodeFormat)}},
    )
    LLM = (
        {"name": "label", "validators": {_V.MIN_LENGTH: 1}},
        {"name": "llm_provider", "validators": {}},
        {"name": "model", "validators": {}},
        {"name": "system_prompt", "validators": {}},
        {"name": "temperature", "validators": {_V.GE: 0.0, _V.LE: 2.0}},
    )
    OUTPUT = (
        {"name": "label", "validators": {_V.MIN_LENGTH: 1}},
        {"name": "format", "validators": {_V.SELECT: list(OutputNodeFormat)}},
    )

    def validate(self, data: dict) -> dict:
        """Validate *data* against this spec's field definitions.

        Args:
            data: The node data dictionary to validate.

        Returns:
            The validated data dictionary.

        Raises:
            ValueError: If any field is missing or fails validation.

        """
        errors = []

        unexpected = set(data.keys()) - {field["name"] for field in self.value}
        if unexpected:
            errors.append(f"Unexpected fields: {', '.join(sorted(unexpected))}")

        for field in self.value:
            name: str = field["name"]

            if name not in data:
                errors.append(f"Missing required field: '{name}'")
                continue

            self._validate_field(
                name=field["name"],
                value=data[name],
                validators=field["validators"],
                errors=errors,
            )

        if errors:
            msg = "; ".join(errors)
            raise ValueError(msg)

        return data

    @staticmethod
    def _validate_field(
        *,
        name: str,
        value: object,
        validators: dict,
        errors: list[str],
    ) -> None:
        """Apply individual validators for a single field.

        Args:
            name: The field name (for error messages).
            value: The field value to check.
            validators: Validator rules from the spec.
            errors: Accumulator list for error messages.

        """
        if ValidatorType.MIN_LENGTH in validators and (
            not isinstance(value, str)
            or len(value) < validators[ValidatorType.MIN_LENGTH]
        ):
            errors.append(
                f"Field '{name}' must be a string with "
                f"min length {validators[ValidatorType.MIN_LENGTH]}"
            )

        if ValidatorType.SELECT in validators:
            allowed = validators[ValidatorType.SELECT]
            if value not in allowed:
                options = ", ".join(str(o) for o in allowed)
                errors.append(f"Field '{name}' must be one of: {options}")

        if ValidatorType.GE in validators:
            threshold = float(validators[ValidatorType.GE])
            if not isinstance(value, (int, float)) or value < threshold:
                errors.append(f"Field '{name}' must be >= {threshold}")

        if ValidatorType.LE in validators:
            threshold = float(validators[ValidatorType.LE])
            if not isinstance(value, (int, float)) or value > threshold:
                errors.append(f"Field '{name}' must be <= {threshold}")

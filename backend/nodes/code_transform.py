"""Code/Transform node handler.

Runs user-authored Python against the upstream text in a RestrictedPython
sandbox: no imports, no file/network I/O, no dangerous builtins (``open``,
``eval``, ``exec``, ``__import__``, ...). The sandbox itself runs on a worker
thread (``asyncio.to_thread``) so it doesn't block the event loop while it
executes. Known limitation: a node whose code never returns (e.g. an infinite
loop) leaks that thread until the worker process recycles — the per-node
timeout can abandon the awaiting coroutine but can't forcibly kill a running
Python thread.
"""

import json
from asyncio import to_thread
from typing import Any, cast

from RestrictedPython import compile_restricted, safe_globals
from RestrictedPython.Eval import default_guarded_getitem, default_guarded_getiter
from RestrictedPython.Guards import guarded_iter_unpack_sequence, safer_getattr

from enums import NodeType, PortType, ValidatorType
from exceptions import ExecutionGraphValidationError
from nodes.base import NodeExecutionContext, NodeExecutionResult
from nodes.definition import NodeDefinition, NodeHandlerDeps, graph_spec
from nodes.value import JSONValue, NodeValue
from schemas import (
    NodeFieldSpec,
    NodeFieldUI,
    NodeFieldWidget,
)

_OUTPUT_VAR = "output"
_INPUT_VAR = "input"
_STRUCTURED_PORT_TYPES = (PortType.TEXT, PortType.JSON, PortType.LIST)

# Safe pure-computation builtins beyond RestrictedPython's minimal default set.
_EXTRA_BUILTINS: dict[str, Any] = {
    "dict": dict,
    "list": list,
    "set": set,
    "tuple": tuple,
    "min": min,
    "max": max,
    "sum": sum,
    "map": map,
    "filter": filter,
    "enumerate": enumerate,
    "reversed": reversed,
    "all": all,
    "any": any,
    "json": json,
}


def _build_restricted_globals() -> dict[str, Any]:
    """Build the global namespace available to sandboxed code."""
    restricted_builtins = dict(safe_globals["__builtins__"])
    restricted_builtins.update(_EXTRA_BUILTINS)
    return {
        "__builtins__": restricted_builtins,
        "_getattr_": safer_getattr,
        "_getitem_": default_guarded_getitem,
        "_getiter_": default_guarded_getiter,
        "_iter_unpack_sequence_": guarded_iter_unpack_sequence,
        "_write_": lambda obj: obj,
    }


class CodeTransformNodeHandler:
    """Handler for code/transform nodes."""

    async def execute(self, context: NodeExecutionContext) -> NodeExecutionResult:
        """Run the node's code against the upstream text.

        Args:
            context: Node execution context.

        Returns:
            The code's ``output`` value, coerced to text.

        Raises:
            ExecutionGraphValidationError: If the code is missing, fails to
                compile, raises while running, or never sets ``output``.

        """
        code = context.node_data.get("code")
        if not isinstance(code, str) or not code.strip():
            message = "Code node requires non-empty code"
            raise ExecutionGraphValidationError(message=message)

        input_type = self._configured_type(context, "input_type")
        output_type = self._configured_type(context, "output_type")
        raw_output = await to_thread(
            self._run_restricted,
            code,
            self._runtime_input(context, input_type),
        )
        return self._build_result(raw_output, output_type)

    @staticmethod
    def _configured_type(context: NodeExecutionContext, field: str) -> PortType:
        """Read one required configurable structured port type."""
        raw_type = context.node_data.get(field)
        try:
            port_type = PortType(raw_type)
        except ValueError as exc:
            raise ExecutionGraphValidationError(
                message=f"Code node has an unsupported {field}"
            ) from exc
        if port_type not in _STRUCTURED_PORT_TYPES:
            raise ExecutionGraphValidationError(
                message=f"Code node {field} must be text, json, or list"
            )
        return port_type

    @staticmethod
    def _runtime_input(
        context: NodeExecutionContext, input_type: PortType
    ) -> JSONValue:
        """Expose text fan-in or one structured parent to restricted code."""
        values = list(context.primary_parent_values) or [context.input_value]
        if input_type is PortType.TEXT:
            return (
                context.joined_parent_text()
                if context.primary_parent_values
                else context.input_text
            )
        if len(values) != 1:
            raise ExecutionGraphValidationError(
                message="Structured Code node inputs require exactly one live edge"
            )
        value = values[0]
        if value.kind is not input_type:
            raise ExecutionGraphValidationError(
                message=(
                    f"Code node expected {input_type.value}, "
                    f"received {value.kind.value}"
                )
            )
        return value.value

    def _run_restricted(self, code: str, input_value: JSONValue) -> object:
        """Compile and execute user code in a restricted sandbox.

        Args:
            code: User-authored Python source.
            input_value: Structured upstream value bound to ``input``.

        Returns:
            The raw JSON-compatible ``output`` value.

        Raises:
            ExecutionGraphValidationError: If compilation or execution fails,
                or the code never assigns to ``output``.

        """
        try:
            byte_code = compile_restricted(code, filename="<code_node>", mode="exec")
        except SyntaxError as exc:
            message = f"Code node has a syntax error: {exc}"
            raise ExecutionGraphValidationError(message=message) from exc

        local_vars: dict[str, Any] = {_INPUT_VAR: input_value}
        try:
            exec(byte_code, _build_restricted_globals(), local_vars)  # noqa: S102
        except ExecutionGraphValidationError:
            raise
        except Exception as exc:
            message = f"Code node raised an error: {exc}"
            raise ExecutionGraphValidationError(message=message) from exc

        if _OUTPUT_VAR not in local_vars:
            message = "Code node must assign a value to 'output'"
            raise ExecutionGraphValidationError(message=message)

        return local_vars[_OUTPUT_VAR]

    def _build_result(
        self, value: object, output_type: PortType
    ) -> NodeExecutionResult:
        """Build the configured typed result without hiding structures in text.

        Args:
            value: The value assigned to ``output`` by user code.
            output_type: Configured type of the node's output port.

        Returns:
            A result whose NodeValue kind matches the configured output port.

        Raises:
            ExecutionGraphValidationError: If the value isn't JSON-serializable.

        """
        if output_type is PortType.TEXT:
            if isinstance(value, str):
                return NodeExecutionResult.text(value)
            try:
                return NodeExecutionResult.text(json.dumps(value))
            except TypeError as exc:
                message = "Code node output must be JSON-serializable"
                raise ExecutionGraphValidationError(message=message) from exc
        if output_type is PortType.LIST:
            if not isinstance(value, list):
                raise ExecutionGraphValidationError(
                    message="Code node list output must be a list"
                )
            try:
                output = NodeValue.list(cast("list[JSONValue]", value))
            except ValueError as exc:
                raise ExecutionGraphValidationError(
                    message="Code node list output must contain JSON values"
                ) from exc
            return NodeExecutionResult(output=output)
        try:
            output = NodeValue.json(cast("JSONValue", value))
        except ValueError as exc:
            raise ExecutionGraphValidationError(
                message="Code node JSON output must be JSON-compatible"
            ) from exc
        return NodeExecutionResult(output=output)


def _build_handler(deps: NodeHandlerDeps) -> CodeTransformNodeHandler:
    """Build a code/transform node handler."""
    del deps
    return CodeTransformNodeHandler()


DEFINITION = NodeDefinition(
    type=NodeType.CODE_TRANSFORM,
    label="Code / Transform",
    icon_key="code_transform",
    graph=graph_spec(
        input_type=PortType.TEXT,
        output_type=PortType.TEXT,
        input_type_field="input_type",
        output_type_field="output_type",
        input_allowed_types=_STRUCTURED_PORT_TYPES,
        output_allowed_types=_STRUCTURED_PORT_TYPES,
    ),
    fields=(
        NodeFieldSpec(
            name="label",
            required=True,
            validators={ValidatorType.MIN_LENGTH.value: 1},
            ui=NodeFieldUI(
                widget=NodeFieldWidget.TEXT,
                label="Label",
                placeholder="Code label",
            ),
            default="Code node",
        ),
        NodeFieldSpec(
            name="input_type",
            required=True,
            validators={
                ValidatorType.SELECT.value: [
                    item.value for item in _STRUCTURED_PORT_TYPES
                ]
            },
            ui=NodeFieldUI(
                widget=NodeFieldWidget.SELECT,
                label="Input type",
                help="Structured JSON/list inputs stay native Python values.",
            ),
            default=PortType.TEXT.value,
        ),
        NodeFieldSpec(
            name="output_type",
            required=True,
            validators={
                ValidatorType.SELECT.value: [
                    item.value for item in _STRUCTURED_PORT_TYPES
                ]
            },
            ui=NodeFieldUI(
                widget=NodeFieldWidget.SELECT,
                label="Output type",
                help="JSON/list outputs remain structured in the workflow runtime.",
            ),
            default=PortType.TEXT.value,
        ),
        NodeFieldSpec(
            name="code",
            required=True,
            validators={ValidatorType.MIN_LENGTH.value: 1},
            ui=NodeFieldUI(
                widget=NodeFieldWidget.TEXTAREA,
                label="Code",
                placeholder="output = input.upper()",
                help=(
                    "Restricted Python. Read the typed upstream value via `input`, "
                    "assign the result to `output`. The `json` module is "
                    "available; imports, file, and network access are not."
                ),
            ),
            default="output = input",
        ),
    ),
    build_handler=_build_handler,
)

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
from typing import Any

from RestrictedPython import compile_restricted, safe_globals
from RestrictedPython.Eval import default_guarded_getitem, default_guarded_getiter
from RestrictedPython.Guards import guarded_iter_unpack_sequence, safer_getattr

from enums import NodeType, PortType, ValidatorType
from exceptions import ExecutionGraphValidationError
from nodes.base import NodeExecutionContext, NodeExecutionResult
from nodes.definition import NodeDefinition, NodeHandlerDeps
from nodes.rendering import upstream_text
from schemas import (
    NodeFieldSpec,
    NodeFieldUI,
    NodeFieldWidget,
    NodeGraphSpec,
)

_OUTPUT_VAR = "output"
_INPUT_VAR = "input"

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

        input_text = upstream_text(context)
        return NodeExecutionResult.text(
            output=await to_thread(self._run_restricted, code, input_text)
        )

    def _run_restricted(self, code: str, input_text: str) -> str:
        """Compile and execute user code in a restricted sandbox.

        Args:
            code: User-authored Python source.
            input_text: The upstream text, bound to the ``input`` variable.

        Returns:
            The coerced ``output`` value.

        Raises:
            ExecutionGraphValidationError: If compilation or execution fails,
                or the code never assigns to ``output``.

        """
        try:
            byte_code = compile_restricted(code, filename="<code_node>", mode="exec")
        except SyntaxError as exc:
            message = f"Code node has a syntax error: {exc}"
            raise ExecutionGraphValidationError(message=message) from exc

        local_vars: dict[str, Any] = {_INPUT_VAR: input_text}
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

        return self._coerce_output(local_vars[_OUTPUT_VAR])

    def _coerce_output(self, value: object) -> str:
        """Coerce the code's output value to text.

        Args:
            value: The value assigned to ``output`` by user code.

        Returns:
            ``value`` unchanged if it's already a string, else its JSON
            encoding.

        Raises:
            ExecutionGraphValidationError: If the value isn't JSON-serializable.

        """
        if isinstance(value, str):
            return value
        try:
            return json.dumps(value)
        except TypeError as exc:
            message = "Code node output must be a string or JSON-serializable value"
            raise ExecutionGraphValidationError(message=message) from exc


def _build_handler(deps: NodeHandlerDeps) -> CodeTransformNodeHandler:
    """Build a code/transform node handler."""
    del deps
    return CodeTransformNodeHandler()


DEFINITION = NodeDefinition(
    type=NodeType.CODE_TRANSFORM,
    label="Code / Transform",
    icon_key="code_transform",
    graph=NodeGraphSpec(
        has_input=True,
        has_output=True,
        input_port=PortType.TEXT,
        output_port=PortType.TEXT,
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
            name="code",
            required=True,
            validators={ValidatorType.MIN_LENGTH.value: 1},
            ui=NodeFieldUI(
                widget=NodeFieldWidget.TEXTAREA,
                label="Code",
                placeholder="output = input.upper()",
                help=(
                    "Restricted Python. Read the upstream text via `input`, "
                    "assign the result to `output`. The `json` module is "
                    "available; imports, file, and network access are not."
                ),
            ),
            default="output = input",
        ),
    ),
    build_handler=_build_handler,
)

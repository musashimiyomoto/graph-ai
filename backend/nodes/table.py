"""Table node loading rows from Google Sheets, CSV, or PostgreSQL."""

import csv
import io
import json
from urllib.parse import parse_qs, urlencode, urljoin, urlparse, urlunparse

import asyncpg
import httpx

from constants import DEFAULT_TIMEOUT
from db.repositories import PostgresConnectionRepository
from enums import NodeType, PortType, TableSource, ValidatorType
from exceptions import ExecutionGraphValidationError, TableSourceError
from nodes.base import NodeExecutionContext, NodeExecutionResult
from nodes.definition import NodeDefinition, NodeHandlerDeps
from nodes.rendering import render_input
from schemas import (
    NodeFieldDataSource,
    NodeFieldDataSourceKind,
    NodeFieldSpec,
    NodeFieldUI,
    NodeFieldVisibility,
    NodeFieldWidget,
    NodeGraphSpec,
)
from utils.encryption import decrypt
from utils.network import blocked_postgres_dsn_reason, blocked_url_reason

_MAX_ROWS = 500
_MAX_COLUMNS = 100
_MAX_CSV_BYTES = 2_000_000
_MAX_REDIRECTS = 3


def _google_sheets_csv_url(raw_url: str) -> str:
    """Convert a public Google Sheets document URL to its CSV export URL."""
    parsed = urlparse(raw_url)
    if parsed.hostname != "docs.google.com":
        raise ExecutionGraphValidationError(
            message="Google Sheets source requires a docs.google.com URL"
        )
    parts = [part for part in parsed.path.split("/") if part]
    try:
        document_index = parts.index("d")
        sheet_id = parts[document_index + 1]
    except (ValueError, IndexError) as exc:
        raise ExecutionGraphValidationError(
            message="Google Sheets URL does not contain a spreadsheet ID"
        ) from exc
    query = parse_qs(parsed.query)
    fragment = parse_qs(parsed.fragment)
    gid = query.get("gid", fragment.get("gid", [None]))[0]
    export_query = {"format": "csv"}
    if gid:
        export_query["gid"] = gid
    return urlunparse(
        (
            "https",
            "docs.google.com",
            f"/spreadsheets/d/{sheet_id}/export",
            "",
            urlencode(export_query),
            "",
        )
    )


def _table_json(columns: list[str], rows: list[list[object]]) -> str:
    """Serialize normalized table data for downstream nodes."""
    return json.dumps(
        {"columns": columns, "rows": rows}, ensure_ascii=False, default=str
    )


class TableNodeHandler:
    """Handler for read-only tabular data sources."""

    def __init__(
        self, postgres_connection_repository: PostgresConnectionRepository
    ) -> None:
        """Initialize handler dependencies."""
        self._postgres_connection_repository = postgres_connection_repository

    async def execute(self, context: NodeExecutionContext) -> NodeExecutionResult:
        """Load and normalize rows from the configured source."""
        source = self._source(context)
        max_rows = self._max_rows(context)
        if source is TableSource.POSTGRES:
            columns, rows = await self._load_postgres(context, max_rows)
        else:
            columns, rows = await self._load_csv(context, source, max_rows)
        return NodeExecutionResult(output=_table_json(columns, rows))

    @staticmethod
    def _source(context: NodeExecutionContext) -> TableSource:
        """Read the source enum from node data."""
        try:
            return TableSource(context.node_data.get("source"))
        except ValueError as exc:
            raise ExecutionGraphValidationError(
                message="Table node has an unsupported source"
            ) from exc

    @staticmethod
    def _max_rows(context: NodeExecutionContext) -> int:
        """Read the bounded row limit."""
        value = context.node_data.get("max_rows")
        if not isinstance(value, int) or not 1 <= value <= _MAX_ROWS:
            raise ExecutionGraphValidationError(
                message=f"Table node max_rows must be in [1, {_MAX_ROWS}]"
            )
        return value

    async def _load_csv(
        self, context: NodeExecutionContext, source: TableSource, max_rows: int
    ) -> tuple[list[str], list[list[object]]]:
        """Fetch and parse a public CSV source."""
        field = (
            "google_sheets_url" if source is TableSource.GOOGLE_SHEETS else "csv_url"
        )
        raw_url = context.node_data.get(field)
        if not isinstance(raw_url, str) or not raw_url.strip():
            raise ExecutionGraphValidationError(message=f"Table node requires {field}")
        rendered = render_input(raw_url, context).strip()
        url = (
            _google_sheets_csv_url(rendered)
            if source is TableSource.GOOGLE_SHEETS
            else rendered
        )
        try:
            async with httpx.AsyncClient(timeout=DEFAULT_TIMEOUT) as client:
                response = await self._get_with_safe_redirects(client, url)
        except httpx.HTTPError as exc:
            raise TableSourceError(message="Table CSV source is unreachable") from exc
        if len(response.content) > _MAX_CSV_BYTES:
            raise ExecutionGraphValidationError(
                message=f"Table CSV response exceeds {_MAX_CSV_BYTES} bytes"
            )
        return self._parse_csv(response.text, max_rows)

    @staticmethod
    async def _get_with_safe_redirects(
        client: httpx.AsyncClient, url: str
    ) -> httpx.Response:
        """Fetch a URL while validating every redirect target against SSRF."""
        current_url = url
        for _redirect in range(_MAX_REDIRECTS + 1):
            reason = await blocked_url_reason(current_url)
            if reason is not None:
                raise ExecutionGraphValidationError(message=reason)
            response = await client.get(current_url, follow_redirects=False)
            if not response.is_redirect:
                response.raise_for_status()
                return response
            location = response.headers.get("location")
            if not location:
                raise TableSourceError(message="Table CSV redirect has no target")
            current_url = urljoin(current_url, location)
        raise TableSourceError(message="Table CSV source has too many redirects")

    @staticmethod
    def _parse_csv(text: str, max_rows: int) -> tuple[list[str], list[list[object]]]:
        """Parse CSV text into a bounded rectangular table."""
        reader = csv.reader(io.StringIO(text))
        try:
            columns = [column.strip() for column in next(reader)]
        except StopIteration as exc:
            raise ExecutionGraphValidationError(message="Table CSV is empty") from exc
        if not columns or any(not column for column in columns):
            raise ExecutionGraphValidationError(
                message="Table CSV requires a non-empty header row"
            )
        if len(columns) > _MAX_COLUMNS:
            raise ExecutionGraphValidationError(
                message=f"Table source exceeds {_MAX_COLUMNS} columns"
            )
        rows: list[list[object]] = []
        for row in reader:
            rows.append((row + [""] * len(columns))[: len(columns)])
            if len(rows) >= max_rows:
                break
        return columns, rows

    async def _load_postgres(
        self, context: NodeExecutionContext, max_rows: int
    ) -> tuple[list[str], list[list[object]]]:
        """Execute one read-only PostgreSQL query."""
        connection_id = context.node_data.get("postgres_connection_id")
        if not isinstance(connection_id, int) or connection_id <= 0:
            raise ExecutionGraphValidationError(
                message="Table node requires a PostgreSQL connection"
            )
        saved = await self._postgres_connection_repository.get_by(
            session=context.session,
            id=connection_id,
            user_id=context.workflow_owner_id,
        )
        if saved is None:
            raise ExecutionGraphValidationError(
                message="Referenced PostgreSQL connection does not exist"
            )
        query = context.node_data.get("query")
        if not isinstance(query, str) or not query.strip():
            raise ExecutionGraphValidationError(
                message="Table node requires a PostgreSQL query"
            )
        query = render_input(query, context).strip().removesuffix(";").strip()
        if ";" in query or not query.lower().startswith(("select", "with")):
            raise ExecutionGraphValidationError(
                message="Table node PostgreSQL query must be one SELECT statement"
            )
        dsn = decrypt(saved.dsn)
        reason = await blocked_postgres_dsn_reason(dsn)
        if reason is not None:
            raise ExecutionGraphValidationError(message=reason)
        connection: asyncpg.Connection | None = None
        try:
            connection = await asyncpg.connect(dsn=dsn, timeout=DEFAULT_TIMEOUT)
            async with connection.transaction(readonly=True):
                records = await connection.fetch(
                    # The query is intentionally user-authored, restricted above
                    # to one SELECT/WITH statement, and runs in a read-only tx.
                    f"SELECT * FROM ({query}) AS graph_ai_table LIMIT {max_rows}"  # noqa: S608
                )
        except (asyncpg.PostgresError, OSError, TimeoutError) as exc:
            raise TableSourceError(message="PostgreSQL table source failed") from exc
        finally:
            if connection is not None:
                await connection.close()
        if not records:
            return [], []
        columns = list(records[0].keys())
        if len(columns) > _MAX_COLUMNS:
            raise ExecutionGraphValidationError(
                message=f"Table source exceeds {_MAX_COLUMNS} columns"
            )
        return columns, [[record[column] for column in columns] for record in records]


def _build_handler(deps: NodeHandlerDeps) -> TableNodeHandler:
    """Build a Table node handler."""
    return TableNodeHandler(deps.postgres_connection_repository)


DEFINITION = NodeDefinition(
    type=NodeType.TABLE,
    label="Table",
    icon_key="table",
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
            ui=NodeFieldUI(widget=NodeFieldWidget.TEXT, label="Label"),
            default="Table node",
        ),
        NodeFieldSpec(
            name="source",
            required=True,
            validators={
                ValidatorType.SELECT.value: [item.value for item in TableSource]
            },
            ui=NodeFieldUI(widget=NodeFieldWidget.SELECT, label="Source"),
            default=TableSource.GOOGLE_SHEETS.value,
        ),
        NodeFieldSpec(
            name="google_sheets_url",
            required=True,
            validators={
                ValidatorType.MIN_LENGTH.value: 1,
                ValidatorType.URL.value: True,
            },
            ui=NodeFieldUI(
                widget=NodeFieldWidget.TEXT,
                label="Google Sheets URL",
                placeholder="https://docs.google.com/spreadsheets/d/...",
                help="The sheet must be publicly readable.",
            ),
            default="",
            visible_when=NodeFieldVisibility(
                field="source", equals=TableSource.GOOGLE_SHEETS.value
            ),
        ),
        NodeFieldSpec(
            name="csv_url",
            required=True,
            validators={
                ValidatorType.MIN_LENGTH.value: 1,
                ValidatorType.URL.value: True,
            },
            ui=NodeFieldUI(
                widget=NodeFieldWidget.TEXT,
                label="CSV URL",
                placeholder="https://example.com/data.csv",
            ),
            default="",
            visible_when=NodeFieldVisibility(
                field="source", equals=TableSource.CSV.value
            ),
        ),
        NodeFieldSpec(
            name="postgres_connection_id",
            required=True,
            validators={ValidatorType.GE.value: 1},
            ui=NodeFieldUI(
                widget=NodeFieldWidget.POSTGRES_CONNECTION,
                label="PostgreSQL connection",
            ),
            datasource=NodeFieldDataSource(
                kind=NodeFieldDataSourceKind.POSTGRES_CONNECTION
            ),
            visible_when=NodeFieldVisibility(
                field="source", equals=TableSource.POSTGRES.value
            ),
        ),
        NodeFieldSpec(
            name="query",
            required=True,
            validators={ValidatorType.MIN_LENGTH.value: 1},
            ui=NodeFieldUI(
                widget=NodeFieldWidget.TEXTAREA,
                label="SELECT query",
                placeholder="SELECT * FROM customers",
                help="Runs in a read-only transaction. {{input}} is supported.",
            ),
            default="SELECT 1 AS value",
            visible_when=NodeFieldVisibility(
                field="source", equals=TableSource.POSTGRES.value
            ),
        ),
        NodeFieldSpec(
            name="max_rows",
            required=True,
            validators={ValidatorType.GE.value: 1, ValidatorType.LE.value: _MAX_ROWS},
            ui=NodeFieldUI(widget=NodeFieldWidget.NUMBER, label="Max rows", step=1),
            default=100,
        ),
    ),
    build_handler=_build_handler,
)

"""Table node source normalization tests."""

from contextlib import AbstractAsyncContextManager
from types import SimpleNamespace
from typing import TYPE_CHECKING, cast

import pytest

from nodes import NodeValue
from nodes.base import NodeExecutionContext
from nodes.table import TableNodeHandler, _google_sheets_csv_url

if TYPE_CHECKING:
    from sqlalchemy.ext.asyncio import AsyncSession

    from db.repositories import PostgresConnectionRepository


class TestTableCsv:
    """CSV parsing and Google Sheets URL tests."""

    def test_parse_csv_normalizes_rows(self) -> None:
        """Short and long rows are normalized to the header width."""
        columns, rows = TableNodeHandler._parse_csv(  # noqa: SLF001
            "name,score\nAda,10\nBob\nCara,8,ignored\n", max_rows=10
        )
        if columns != ["name", "score"]:
            pytest.fail("CSV header was not preserved")
        if rows != [["Ada", "10"], ["Bob", ""], ["Cara", "8"]]:
            pytest.fail("CSV rows were not normalized")

    def test_google_sheets_url_becomes_csv_export(self) -> None:
        """A document URL keeps its sheet gid in the CSV export URL."""
        url = _google_sheets_csv_url(
            "https://docs.google.com/spreadsheets/d/sheet-id/edit?gid=42"
        )
        if url != (
            "https://docs.google.com/spreadsheets/d/sheet-id/export?format=csv&gid=42"
        ):
            pytest.fail("Google Sheets URL was not converted correctly")


class _Transaction(AbstractAsyncContextManager[None]):
    """No-op asyncpg transaction stub."""

    async def __aenter__(self) -> None:
        """Enter the transaction."""

    async def __aexit__(self, *args: object) -> None:
        """Exit the transaction."""
        del args


class _Record(dict[str, object]):
    """Mapping-shaped asyncpg record stand-in."""


class _Connection:
    """Captures the generated bounded query."""

    def __init__(self) -> None:
        """Initialize captured state."""
        self.query = ""
        self.closed = False

    def transaction(self, *, readonly: bool) -> _Transaction:
        """Require a read-only transaction."""
        if not readonly:
            pytest.fail("Table query must run read-only")
        return _Transaction()

    async def fetch(self, query: str) -> list[_Record]:
        """Capture the query and return one row."""
        self.query = query
        return [_Record(id=1, name="Ada")]

    async def close(self) -> None:
        """Record connection cleanup."""
        self.closed = True


class _Repository:
    """Returns one owned encrypted connection row."""

    async def get_by(self, *args: object, **kwargs: object) -> SimpleNamespace:
        """Return the saved connection."""
        del args, kwargs
        return SimpleNamespace(dsn="encrypted")


class TestTablePostgres:
    """PostgreSQL query safety and output tests."""

    @pytest.mark.asyncio
    async def test_runs_select_readonly_with_limit(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """A SELECT is wrapped in a server-side row limit and normalized."""
        connection = _Connection()

        async def connect(*args: object, **kwargs: object) -> _Connection:
            """Return the connection stub."""
            del args, kwargs
            return connection

        async def allowed(_dsn: str) -> None:
            """Allow the fake DSN."""

        monkeypatch.setattr("nodes.table.asyncpg.connect", connect)
        monkeypatch.setattr("nodes.table.decrypt", lambda _value: "postgresql://db")
        monkeypatch.setattr("nodes.table.blocked_postgres_dsn_reason", allowed)
        handler = TableNodeHandler(cast("PostgresConnectionRepository", _Repository()))
        result = await handler.execute(
            NodeExecutionContext(
                session=cast("AsyncSession", None),
                workflow_owner_id=1,
                node_data={
                    "source": "postgres",
                    "postgres_connection_id": 1,
                    "query": "SELECT id, name FROM people;",
                    "max_rows": 25,
                },
                parent_values=[NodeValue.text("input")],
                input_value=NodeValue.text("input"),
            )
        )
        if "LIMIT 25" not in connection.query:
            pytest.fail("PostgreSQL query was not bounded")
        if (
            result.output.require_text()
            != '{"columns": ["id", "name"], "rows": [[1, "Ada"]]}'
        ):
            pytest.fail("PostgreSQL rows were not normalized")
        if not connection.closed:
            pytest.fail("PostgreSQL connection was not closed")

"""Add OpenAI and Anthropic LLM provider types.

Revision ID: c9e4b1a7d3f6
Revises: b4a927e1c8d5
Create Date: 2026-07-11 12:00:00.000000

The `llmprovidertype` enum has only ever had `OLLAMA` migrated into it —
no prior revision added `OPENAI`/`ANTHROPIC`, even though the app has
supported creating providers of those types since Phase 2. Without this,
creating an OpenAI or Anthropic provider fails at the database with
`invalid input value for enum llmprovidertype`.
"""

from collections.abc import Sequence

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "c9e4b1a7d3f6"
down_revision: str | None = "b4a927e1c8d5"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Upgrade database schema."""
    op.execute("ALTER TYPE llmprovidertype ADD VALUE IF NOT EXISTS 'OPENAI'")
    op.execute("ALTER TYPE llmprovidertype ADD VALUE IF NOT EXISTS 'ANTHROPIC'")


def downgrade() -> None:
    """Downgrade database schema.

    PostgreSQL enum values are not safely removable in-place, so this is a no-op.
    """

"""Make llm_providers api_key nullable and add config."""

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision = "b3e7aa4c2a1d"
down_revision = "96078f6fa6ee"
branch_labels = None
depends_on = None


def upgrade() -> None:
    """Apply the schema changes."""
    op.alter_column(
        "llm_providers",
        "api_key",
        existing_type=sa.Text(),
        nullable=True,
    )
    op.add_column(
        "llm_providers",
        sa.Column(
            "config",
            postgresql.JSONB(astext_type=sa.Text()),
            server_default="{}",
            nullable=False,
            comment="Provider configuration",
        ),
    )


def downgrade() -> None:
    """Revert the schema changes."""
    op.drop_column("llm_providers", "config")
    op.alter_column(
        "llm_providers",
        "api_key",
        existing_type=sa.Text(),
        nullable=False,
    )

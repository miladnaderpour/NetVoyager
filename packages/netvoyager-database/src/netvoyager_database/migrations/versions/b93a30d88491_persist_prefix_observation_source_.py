
"""persist prefix observation source context

Revision ID: b93a30d88491
Revises: 854b3e8ca620
Create Date: 2026-10-24 15:01:27.731250
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa



revision: str = 'b93a30d88491'
down_revision: Union[str, Sequence[str], None] = '854b3e8ca620'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Persist source identity for prefix observations."""
    op.add_column(
        "prefix_observations",
        sa.Column(
            "source_name",
            sa.String(length=255),
            nullable=True,
        ),
    )

    op.add_column(
        "prefix_observations",
        sa.Column(
            "source_method",
            sa.String(length=80),
            nullable=True,
        ),
    )


def downgrade() -> None:
    """Remove source identity from prefix observations."""
    op.drop_column("prefix_observations", "source_method")
    op.drop_column("prefix_observations", "source_name")
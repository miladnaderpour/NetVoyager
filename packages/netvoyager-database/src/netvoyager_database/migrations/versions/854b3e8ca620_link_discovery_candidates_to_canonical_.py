
"""link discovery candidates to canonical prefixes

Revision ID: 854b3e8ca620
Revises: 8ec9bf972a74
Create Date: 2026-10-24 10:37:04.624122
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa



revision: str = '854b3e8ca620'
down_revision: Union[str, Sequence[str], None] = '8ec9bf972a74'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Enforce canonical prefix references for discovery candidates."""
    with op.batch_alter_table(
        "prefix_discovery_candidates",
        recreate="always",
    ) as batch_op:
        batch_op.create_foreign_key(
            "fk_prefix_discovery_candidates_resolved_prefix_id",
            "network_prefixes",
            ["resolved_prefix_id"],
            ["id"],
        )


def downgrade() -> None:
    """Remove canonical prefix reference constraint."""
    with op.batch_alter_table(
        "prefix_discovery_candidates",
        recreate="always",
    ) as batch_op:
        batch_op.drop_constraint(
            "fk_prefix_discovery_candidates_resolved_prefix_id",
            type_="foreignkey",
        )
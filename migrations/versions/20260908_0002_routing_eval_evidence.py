"""routing rule evaluation evidence policy

Revision ID: 20260908_0002
Revises: 20260509_0001
Create Date: 2026-09-08 10:00:00
"""

from collections.abc import Sequence

from alembic import op
import sqlalchemy as sa

revision: str = "20260908_0002"
down_revision: str | Sequence[str] | None = "20260509_0001"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column(
        "routing_rules",
        sa.Column("allow_unverified", sa.Boolean(), nullable=False, server_default=sa.false()),
    )
    op.add_column(
        "routing_rules",
        sa.Column("allow_stale_evidence", sa.Boolean(), nullable=False, server_default=sa.false()),
    )
    op.add_column("routing_rules", sa.Column("required_eval_suite_id", sa.String(), nullable=True))


def downgrade() -> None:
    op.drop_column("routing_rules", "required_eval_suite_id")
    op.drop_column("routing_rules", "allow_stale_evidence")
    op.drop_column("routing_rules", "allow_unverified")

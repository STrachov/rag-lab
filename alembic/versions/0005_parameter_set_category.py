"""parameter set category

Revision ID: 0005_parameter_set_category
Revises: 0004_asset_manifest_cascade
Create Date: 2026-05-13
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0005_parameter_set_category"
down_revision: str | None = "0004_asset_manifest_cascade"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column(
        "parameter_sets",
        sa.Column("category", sa.String(length=50), nullable=False, server_default="general"),
    )
    op.alter_column("parameter_sets", "category", server_default=None)


def downgrade() -> None:
    op.drop_column("parameter_sets", "category")

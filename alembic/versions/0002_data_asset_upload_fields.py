"""data asset upload fields

Revision ID: 0002_data_asset_upload_fields
Revises: 0001_project_model
Create Date: 2026-05-11
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0002_data_asset_upload_fields"
down_revision: str | None = "0001_project_model"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column(
        "data_assets",
        sa.Column("data_format", sa.String(length=50), nullable=False, server_default="mixed"),
    )
    op.add_column(
        "data_assets",
        sa.Column("storage_kind", sa.String(length=50), nullable=False, server_default="uploaded"),
    )
    op.add_column(
        "data_assets",
        sa.Column("status", sa.String(length=50), nullable=False, server_default="ready"),
    )


def downgrade() -> None:
    op.drop_column("data_assets", "status")
    op.drop_column("data_assets", "storage_kind")
    op.drop_column("data_assets", "data_format")

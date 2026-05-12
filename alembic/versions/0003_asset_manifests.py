"""data asset manifest snapshots

Revision ID: 0003_asset_manifests
Revises: 0002_data_asset_upload_fields
Create Date: 2026-05-12
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0003_asset_manifests"
down_revision: str | None = "0002_data_asset_upload_fields"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "data_asset_manifests",
        sa.Column("id", sa.String(length=32), nullable=False),
        sa.Column("data_asset_id", sa.String(length=32), nullable=False),
        sa.Column("manifest_hash", sa.String(length=255), nullable=False),
        sa.Column("manifest_json", sa.JSON(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["data_asset_id"], ["data_assets.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.add_column(
        "saved_experiments",
        sa.Column("data_asset_manifest_hash", sa.String(length=255), nullable=True),
    )


def downgrade() -> None:
    op.drop_column("saved_experiments", "data_asset_manifest_hash")
    op.drop_table("data_asset_manifests")

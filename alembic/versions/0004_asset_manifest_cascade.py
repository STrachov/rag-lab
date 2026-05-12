"""asset manifest cascade

Revision ID: 0004_asset_manifest_cascade
Revises: 0003_asset_manifests
Create Date: 2026-05-12
"""

from collections.abc import Sequence

from alembic import op

revision: str = "0004_asset_manifest_cascade"
down_revision: str | None = "0003_asset_manifests"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.drop_constraint(
        "data_asset_manifests_data_asset_id_fkey",
        "data_asset_manifests",
        type_="foreignkey",
    )
    op.create_foreign_key(
        "data_asset_manifests_data_asset_id_fkey",
        "data_asset_manifests",
        "data_assets",
        ["data_asset_id"],
        ["id"],
        ondelete="CASCADE",
    )


def downgrade() -> None:
    op.drop_constraint(
        "data_asset_manifests_data_asset_id_fkey",
        "data_asset_manifests",
        type_="foreignkey",
    )
    op.create_foreign_key(
        "data_asset_manifests_data_asset_id_fkey",
        "data_asset_manifests",
        "data_assets",
        ["data_asset_id"],
        ["id"],
    )

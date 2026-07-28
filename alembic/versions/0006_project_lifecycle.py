"""add project lifecycle constraint

Revision ID: 0006_project_lifecycle
Revises: 0005_parameter_set_category
Create Date: 2026-07-27
"""

from collections.abc import Sequence

from alembic import op

revision: str = "0006_project_lifecycle"
down_revision: str | None = "0005_parameter_set_category"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.execute(
        """
        UPDATE projects
        SET status = 'archived'
        WHERE status NOT IN ('active', 'archived')
        """
    )
    op.create_check_constraint(
        "ck_projects_status",
        "projects",
        "status IN ('active', 'archived')",
    )


def downgrade() -> None:
    op.drop_constraint("ck_projects_status", "projects", type_="check")

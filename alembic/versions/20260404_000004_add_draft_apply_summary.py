"""add extraction draft apply summary

Revision ID: 20260404_000004
Revises: 20260404_000003
Create Date: 2026-04-04 16:30:00
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "20260404_000004"
down_revision: Union[str, None] = "20260404_000003"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def _has_column(inspector: sa.Inspector, table_name: str, column_name: str) -> bool:
    return any(column["name"] == column_name for column in inspector.get_columns(table_name))


def upgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    if not _has_column(inspector, "extraction_drafts", "apply_summary_json"):
        op.add_column("extraction_drafts", sa.Column("apply_summary_json", sa.JSON(), nullable=True))


def downgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    if _has_column(inspector, "extraction_drafts", "apply_summary_json"):
        op.drop_column("extraction_drafts", "apply_summary_json")

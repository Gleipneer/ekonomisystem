"""document review workflow fields

Revision ID: 20260404_000003
Revises: 20260404_000002
Create Date: 2026-04-04 14:10:00
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "20260404_000003"
down_revision: Union[str, None] = "20260404_000002"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def _has_column(inspector: sa.Inspector, table_name: str, column_name: str) -> bool:
    return any(column["name"] == column_name for column in inspector.get_columns(table_name))


def upgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)

    if not _has_column(inspector, "documents", "processing_error"):
        op.add_column("documents", sa.Column("processing_error", sa.Text(), nullable=True))

    inspector = sa.inspect(bind)
    if not _has_column(inspector, "extraction_drafts", "review_json"):
        op.add_column("extraction_drafts", sa.Column("review_json", sa.JSON(), nullable=True))
    inspector = sa.inspect(bind)
    if not _has_column(inspector, "extraction_drafts", "canonical_target_entity_type"):
        op.add_column("extraction_drafts", sa.Column("canonical_target_entity_type", sa.String(), nullable=True))
    inspector = sa.inspect(bind)
    if not _has_column(inspector, "extraction_drafts", "canonical_target_entity_id"):
        op.add_column("extraction_drafts", sa.Column("canonical_target_entity_id", sa.Integer(), nullable=True))
    inspector = sa.inspect(bind)
    if not _has_column(inspector, "extraction_drafts", "review_error"):
        op.add_column("extraction_drafts", sa.Column("review_error", sa.Text(), nullable=True))
    inspector = sa.inspect(bind)
    if not _has_column(inspector, "extraction_drafts", "applied_at"):
        op.add_column("extraction_drafts", sa.Column("applied_at", sa.DateTime(), nullable=True))


def downgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)

    for table_name, column_name in [
        ("extraction_drafts", "applied_at"),
        ("extraction_drafts", "review_error"),
        ("extraction_drafts", "canonical_target_entity_id"),
        ("extraction_drafts", "canonical_target_entity_type"),
        ("extraction_drafts", "review_json"),
        ("documents", "processing_error"),
    ]:
        inspector = sa.inspect(bind)
        if _has_column(inspector, table_name, column_name):
            op.drop_column(table_name, column_name)

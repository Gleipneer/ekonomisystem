"""add merchant aliases table

Revision ID: 20260404_000002
Revises: 20260402_000001
Create Date: 2026-04-04 11:10:00
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "20260404_000002"
down_revision: Union[str, None] = "20260402_000001"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def _has_table(inspector: sa.Inspector, table_name: str) -> bool:
    return table_name in inspector.get_table_names()


def _has_index(inspector: sa.Inspector, table_name: str, index_name: str) -> bool:
    return any(index["name"] == index_name for index in inspector.get_indexes(table_name))


def upgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)

    if not _has_table(inspector, "merchant_aliases"):
        op.create_table(
            "merchant_aliases",
            sa.Column("id", sa.Integer(), nullable=False),
            sa.Column("household_id", sa.Integer(), nullable=False),
            sa.Column("alias", sa.String(), nullable=False),
            sa.Column("canonical_name", sa.String(), nullable=False),
            sa.Column("category_hint", sa.String(), nullable=True),
            sa.Column("created_at", sa.DateTime(), nullable=True),
            sa.ForeignKeyConstraint(["household_id"], ["households.id"], ondelete="CASCADE"),
            sa.PrimaryKeyConstraint("id"),
        )

    inspector = sa.inspect(bind)
    if _has_table(inspector, "merchant_aliases") and not _has_index(
        inspector, "merchant_aliases", "ix_merchant_aliases_id"
    ):
        op.create_index("ix_merchant_aliases_id", "merchant_aliases", ["id"], unique=False)


def downgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    if _has_table(inspector, "merchant_aliases") and _has_index(
        inspector, "merchant_aliases", "ix_merchant_aliases_id"
    ):
        op.drop_index("ix_merchant_aliases_id", table_name="merchant_aliases")
    if _has_table(inspector, "merchant_aliases"):
        op.drop_table("merchant_aliases")

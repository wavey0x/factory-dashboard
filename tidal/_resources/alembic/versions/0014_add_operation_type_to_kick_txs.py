"""add operation_type to kick_txs

Revision ID: 0014_add_operation_type_to_kick_txs
Revises: 0013_add_fee_burners_and_source_fields
Create Date: 2026-03-26 08:30:00.000000
"""

from __future__ import annotations

from alembic import op
import sqlalchemy as sa


revision = "0014_add_operation_type_to_kick_txs"
down_revision = "0013_add_fee_burners_and_source_fields"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "kick_txs",
        sa.Column("operation_type", sa.String(), nullable=True, server_default="kick"),
    )
    op.execute("UPDATE kick_txs SET operation_type = 'kick' WHERE operation_type IS NULL")
    with op.batch_alter_table("kick_txs") as batch_op:
        batch_op.alter_column(
            "operation_type",
            existing_type=sa.String(),
            nullable=False,
            server_default="kick",
        )


def downgrade() -> None:
    op.drop_column("kick_txs", "operation_type")

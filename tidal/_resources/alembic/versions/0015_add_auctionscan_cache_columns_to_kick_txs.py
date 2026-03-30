"""add auctionscan cache columns to kick_txs

Revision ID: 0015_add_auctionscan_cache_columns_to_kick_txs
Revises: 0014_add_operation_type_to_kick_txs
Create Date: 2026-03-26 13:30:00.000000
"""

from __future__ import annotations

from alembic import op
import sqlalchemy as sa


revision = "0015_add_auctionscan_cache_columns_to_kick_txs"
down_revision = "0014_add_operation_type_to_kick_txs"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("kick_txs", sa.Column("auctionscan_round_id", sa.Integer(), nullable=True))
    op.add_column("kick_txs", sa.Column("auctionscan_last_checked_at", sa.String(), nullable=True))
    op.add_column("kick_txs", sa.Column("auctionscan_matched_at", sa.String(), nullable=True))


def downgrade() -> None:
    op.drop_column("kick_txs", "auctionscan_matched_at")
    op.drop_column("kick_txs", "auctionscan_last_checked_at")
    op.drop_column("kick_txs", "auctionscan_round_id")

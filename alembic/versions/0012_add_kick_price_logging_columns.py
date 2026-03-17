"""add kick price audit logging columns to kick_txs

Revision ID: 0012_add_kick_price_logging_columns
Revises: 0011_add_minimum_price_to_kick_txs
Create Date: 2026-03-17 12:00:00.000000

"""
from __future__ import annotations

from alembic import op
import sqlalchemy as sa


revision = "0012_add_kick_price_logging_columns"
down_revision = "0011_add_minimum_price_to_kick_txs"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("kick_txs", sa.Column("quote_amount", sa.Text(), nullable=True))
    op.add_column("kick_txs", sa.Column("quote_response_json", sa.Text(), nullable=True))
    op.add_column("kick_txs", sa.Column("start_price_buffer_bps", sa.Integer(), nullable=True))
    op.add_column("kick_txs", sa.Column("min_price_buffer_bps", sa.Integer(), nullable=True))
    op.add_column("kick_txs", sa.Column("token_symbol", sa.String(), nullable=True))
    op.add_column("kick_txs", sa.Column("want_address", sa.String(), nullable=True))
    op.add_column("kick_txs", sa.Column("want_symbol", sa.String(), nullable=True))
    op.add_column("kick_txs", sa.Column("normalized_balance", sa.Text(), nullable=True))


def downgrade() -> None:
    op.drop_column("kick_txs", "normalized_balance")
    op.drop_column("kick_txs", "want_symbol")
    op.drop_column("kick_txs", "want_address")
    op.drop_column("kick_txs", "token_symbol")
    op.drop_column("kick_txs", "min_price_buffer_bps")
    op.drop_column("kick_txs", "start_price_buffer_bps")
    op.drop_column("kick_txs", "quote_response_json")
    op.drop_column("kick_txs", "quote_amount")

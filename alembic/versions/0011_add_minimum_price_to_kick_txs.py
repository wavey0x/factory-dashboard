"""add minimum_price to kick_txs

Revision ID: 0011_add_minimum_price_to_kick_txs
Revises: 0010_add_deposit_limit_to_vaults
Create Date: 2026-03-16 22:00:00.000000

"""
from __future__ import annotations

from alembic import op
import sqlalchemy as sa


revision = "0011_add_minimum_price_to_kick_txs"
down_revision = "0010_add_deposit_limit_to_vaults"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("kick_txs", sa.Column("minimum_price", sa.Text(), nullable=True))


def downgrade() -> None:
    op.drop_column("kick_txs", "minimum_price")

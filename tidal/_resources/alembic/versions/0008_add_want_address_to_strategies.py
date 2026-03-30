"""add want_address to strategies

Revision ID: 0008_add_want_address_to_strategies
Revises: 0007_add_txn_runs_and_kick_txs
Create Date: 2026-03-11 12:00:00.000000

"""
from __future__ import annotations

from alembic import op
import sqlalchemy as sa


revision = "0008_add_want_address_to_strategies"
down_revision = "0007_add_txn_runs_and_kick_txs"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("strategies", sa.Column("want_address", sa.String(), nullable=True))


def downgrade() -> None:
    op.drop_column("strategies", "want_address")

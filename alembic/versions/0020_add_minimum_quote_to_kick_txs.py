"""add minimum_quote to kick_txs

Revision ID: 0020_add_minimum_quote_to_kick_txs
Revises: 0019_add_api_keys
Create Date: 2026-03-29 23:20:00.000000
"""

from __future__ import annotations

from alembic import op
import sqlalchemy as sa


revision = "0020_add_minimum_quote_to_kick_txs"
down_revision = "0019_add_api_keys"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("kick_txs", sa.Column("minimum_quote", sa.Text(), nullable=True))


def downgrade() -> None:
    op.drop_column("kick_txs", "minimum_quote")

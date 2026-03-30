"""add kick log listing indexes

Revision ID: 0021_add_kick_log_listing_indexes
Revises: 0020_add_minimum_quote_to_kick_txs
Create Date: 2026-03-30 10:00:00.000000
"""

from __future__ import annotations

from alembic import op


revision = "0021_add_kick_log_listing_indexes"
down_revision = "0020_add_minimum_quote_to_kick_txs"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_index("ix_kick_txs_created", "kick_txs", ["created_at"])
    op.create_index("ix_kick_txs_status_created", "kick_txs", ["status", "created_at"])
    op.create_index("ix_kick_txs_auction_created", "kick_txs", ["auction_address", "created_at"])
    op.create_index("ix_kick_txs_run_created", "kick_txs", ["run_id", "created_at"])


def downgrade() -> None:
    op.drop_index("ix_kick_txs_run_created", table_name="kick_txs")
    op.drop_index("ix_kick_txs_auction_created", table_name="kick_txs")
    op.drop_index("ix_kick_txs_status_created", table_name="kick_txs")
    op.drop_index("ix_kick_txs_created", table_name="kick_txs")

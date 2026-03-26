"""add auction enabled token cache tables

Revision ID: 0016_add_auction_enabled_token_cache
Revises: 0015_add_auctionscan_cache_columns_to_kick_txs
Create Date: 2026-03-26 15:30:00.000000
"""

from __future__ import annotations

from alembic import op
import sqlalchemy as sa


revision = "0016_add_auction_enabled_token_cache"
down_revision = "0015_add_auctionscan_cache_columns_to_kick_txs"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "auction_enabled_tokens_latest",
        sa.Column("auction_address", sa.String(), nullable=False),
        sa.Column("token_address", sa.String(), nullable=False),
        sa.Column("active", sa.Integer(), nullable=False, server_default="1"),
        sa.Column("first_seen_at", sa.String(), nullable=False),
        sa.Column("last_seen_at", sa.String(), nullable=False),
        sa.PrimaryKeyConstraint("auction_address", "token_address"),
    )
    op.create_index(
        "ix_auction_enabled_tokens_latest_active",
        "auction_enabled_tokens_latest",
        ["auction_address", "active"],
        unique=False,
    )

    op.create_table(
        "auction_enabled_token_scans",
        sa.Column("auction_address", sa.String(), nullable=False),
        sa.Column("scanned_at", sa.String(), nullable=False),
        sa.Column("block_number", sa.Integer(), nullable=True),
        sa.Column("status", sa.String(), nullable=False),
        sa.Column("error_message", sa.Text(), nullable=True),
        sa.PrimaryKeyConstraint("auction_address"),
    )


def downgrade() -> None:
    op.drop_table("auction_enabled_token_scans")
    op.drop_index("ix_auction_enabled_tokens_latest_active", table_name="auction_enabled_tokens_latest")
    op.drop_table("auction_enabled_tokens_latest")

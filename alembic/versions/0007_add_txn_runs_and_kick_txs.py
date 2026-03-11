"""add txn_runs and kick_txs tables

Revision ID: 0007_add_txn_runs_and_kick_txs
Revises: 0006_add_strategy_auction_and_token_logo_fields
Create Date: 2026-03-11 12:00:00.000000

"""
from __future__ import annotations

from alembic import op
import sqlalchemy as sa


revision = "0007_add_txn_runs_and_kick_txs"
down_revision = "0006_add_strategy_auction_and_token_logo_fields"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "txn_runs",
        sa.Column("run_id", sa.String(), primary_key=True),
        sa.Column("started_at", sa.String(), nullable=False),
        sa.Column("finished_at", sa.String(), nullable=True),
        sa.Column("status", sa.String(), nullable=False),
        sa.Column("candidates_found", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("kicks_attempted", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("kicks_succeeded", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("kicks_failed", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("live", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("error_summary", sa.Text(), nullable=True),
    )

    op.create_table(
        "kick_txs",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("run_id", sa.String(), nullable=False),
        sa.Column("strategy_address", sa.String(), nullable=False),
        sa.Column("token_address", sa.String(), nullable=False),
        sa.Column("auction_address", sa.String(), nullable=False),
        sa.Column("sell_amount", sa.Text(), nullable=True),
        sa.Column("starting_price", sa.Text(), nullable=True),
        sa.Column("price_usd", sa.Text(), nullable=True),
        sa.Column("usd_value", sa.Text(), nullable=True),
        sa.Column("status", sa.String(), nullable=False),
        sa.Column("tx_hash", sa.String(), nullable=True),
        sa.Column("gas_used", sa.Integer(), nullable=True),
        sa.Column("gas_price_gwei", sa.Text(), nullable=True),
        sa.Column("block_number", sa.Integer(), nullable=True),
        sa.Column("error_message", sa.Text(), nullable=True),
        sa.Column("created_at", sa.String(), nullable=False),
    )

    op.create_index(
        "ix_kick_txs_strategy_token_created",
        "kick_txs",
        ["strategy_address", "token_address", sa.text("created_at DESC")],
    )


def downgrade() -> None:
    op.drop_index("ix_kick_txs_strategy_token_created", table_name="kick_txs")
    op.drop_table("kick_txs")
    op.drop_table("txn_runs")

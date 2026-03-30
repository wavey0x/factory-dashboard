"""add api action audit tables

Revision ID: 0018_add_api_action_audit_tables
Revises: 0017_add_kick_operation_detail_columns
Create Date: 2026-03-28 12:00:00.000000
"""

from __future__ import annotations

from alembic import op
import sqlalchemy as sa


revision = "0018_add_api_action_audit_tables"
down_revision = "0017_add_kick_operation_detail_columns"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "api_actions",
        sa.Column("action_id", sa.String(), nullable=False),
        sa.Column("action_type", sa.String(), nullable=False),
        sa.Column("status", sa.String(), nullable=False),
        sa.Column("operator_id", sa.String(), nullable=False),
        sa.Column("sender", sa.String(), nullable=True),
        sa.Column("resource_address", sa.String(), nullable=True),
        sa.Column("auction_address", sa.String(), nullable=True),
        sa.Column("source_address", sa.String(), nullable=True),
        sa.Column("token_address", sa.String(), nullable=True),
        sa.Column("request_json", sa.Text(), nullable=False),
        sa.Column("preview_json", sa.Text(), nullable=False),
        sa.Column("error_message", sa.Text(), nullable=True),
        sa.Column("created_at", sa.String(), nullable=False),
        sa.Column("updated_at", sa.String(), nullable=False),
        sa.PrimaryKeyConstraint("action_id"),
    )
    op.create_index("ix_api_actions_status_created", "api_actions", ["status", "created_at"], unique=False)
    op.create_index("ix_api_actions_operator_created", "api_actions", ["operator_id", "created_at"], unique=False)

    op.create_table(
        "api_action_transactions",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("action_id", sa.String(), nullable=False),
        sa.Column("tx_index", sa.Integer(), nullable=False),
        sa.Column("operation", sa.String(), nullable=False),
        sa.Column("to_address", sa.String(), nullable=False),
        sa.Column("data", sa.Text(), nullable=False),
        sa.Column("value", sa.String(), nullable=False),
        sa.Column("chain_id", sa.Integer(), nullable=False),
        sa.Column("gas_estimate", sa.Integer(), nullable=True),
        sa.Column("gas_limit", sa.Integer(), nullable=True),
        sa.Column("tx_hash", sa.String(), nullable=True),
        sa.Column("broadcast_at", sa.String(), nullable=True),
        sa.Column("receipt_status", sa.String(), nullable=True),
        sa.Column("block_number", sa.Integer(), nullable=True),
        sa.Column("gas_used", sa.Integer(), nullable=True),
        sa.Column("gas_price_gwei", sa.Text(), nullable=True),
        sa.Column("error_message", sa.Text(), nullable=True),
        sa.Column("created_at", sa.String(), nullable=False),
        sa.Column("updated_at", sa.String(), nullable=False),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        "ix_api_action_transactions_action_tx_index",
        "api_action_transactions",
        ["action_id", "tx_index"],
        unique=True,
    )
    op.create_index(
        "ix_api_action_transactions_receipt_pending",
        "api_action_transactions",
        ["tx_hash", "receipt_status", "broadcast_at"],
        unique=False,
    )


def downgrade() -> None:
    op.drop_index("ix_api_action_transactions_receipt_pending", table_name="api_action_transactions")
    op.drop_index("ix_api_action_transactions_action_tx_index", table_name="api_action_transactions")
    op.drop_table("api_action_transactions")
    op.drop_index("ix_api_actions_operator_created", table_name="api_actions")
    op.drop_index("ix_api_actions_status_created", table_name="api_actions")
    op.drop_table("api_actions")

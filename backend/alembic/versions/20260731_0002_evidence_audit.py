"""add evidence audit fields

Revision ID: 20260731_0002
Revises: 20260713_0001
Create Date: 2026-07-31
"""
from alembic import op
import sqlalchemy as sa


revision = "20260731_0002"
down_revision = "20260713_0001"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("company_reports", sa.Column("scoring_status", sa.String(length=40), nullable=True))
    op.add_column("company_reports", sa.Column("model_version", sa.String(length=40), nullable=True))
    op.add_column("company_reports", sa.Column("input_snapshot_hash", sa.String(length=64), nullable=True))
    op.add_column("company_reports", sa.Column("evidence_json", sa.JSON(), nullable=True))
    op.create_index("ix_company_reports_input_snapshot_hash", "company_reports", ["input_snapshot_hash"])


def downgrade() -> None:
    op.drop_index("ix_company_reports_input_snapshot_hash", table_name="company_reports")
    op.drop_column("company_reports", "evidence_json")
    op.drop_column("company_reports", "input_snapshot_hash")
    op.drop_column("company_reports", "model_version")
    op.drop_column("company_reports", "scoring_status")

"""add canonical name, confidence, and coverage to stored scores

Public-track ratings persist a number with separate confidence and coverage.
Canonical names keep Cargill / Cargill Inc on the same history and watchlist key.

Revision ID: 20260815_0004
Revises: 20260808_0003
Create Date: 2026-08-15
"""
from alembic import op
import sqlalchemy as sa


revision = "20260815_0004"
down_revision = "20260808_0003"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("company_searches", sa.Column("canonical_name", sa.String(length=180), nullable=True))
    op.add_column("company_searches", sa.Column("confidence", sa.Float(), nullable=True))
    op.add_column("company_searches", sa.Column("coverage", sa.Float(), nullable=True))
    op.create_index("ix_company_searches_canonical_name", "company_searches", ["canonical_name"])

    op.add_column("company_reports", sa.Column("canonical_name", sa.String(length=180), nullable=True))
    op.add_column("company_reports", sa.Column("confidence", sa.Float(), nullable=True))
    op.add_column("company_reports", sa.Column("coverage", sa.Float(), nullable=True))
    op.create_index("ix_company_reports_canonical_name", "company_reports", ["canonical_name"])


def downgrade() -> None:
    op.drop_index("ix_company_reports_canonical_name", table_name="company_reports")
    op.drop_column("company_reports", "coverage")
    op.drop_column("company_reports", "confidence")
    op.drop_column("company_reports", "canonical_name")
    op.drop_index("ix_company_searches_canonical_name", table_name="company_searches")
    op.drop_column("company_searches", "coverage")
    op.drop_column("company_searches", "confidence")
    op.drop_column("company_searches", "canonical_name")

"""allow a null score for unrated companies

An unrated company has no PerpScore. Previously the scorer emitted a neutral
500 placeholder that was written into NOT NULL columns, leaving rows that any
later query or export would read as a real mid-range score.

Revision ID: 20260808_0003
Revises: 20260731_0002
Create Date: 2026-08-08
"""
from alembic import op
import sqlalchemy as sa


revision = "20260808_0003"
down_revision = "20260731_0002"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("company_searches", sa.Column("scoring_status", sa.String(length=40), nullable=True))
    op.add_column("saved_companies", sa.Column("scoring_status", sa.String(length=40), nullable=True))
    with op.batch_alter_table("company_searches") as batch:
        batch.alter_column("private_score", existing_type=sa.Integer(), nullable=True)
    with op.batch_alter_table("company_reports") as batch:
        batch.alter_column("private_score", existing_type=sa.Integer(), nullable=True)

    # Backfill: rows recorded while the placeholder was in effect are unrated and
    # must not keep a numeric score.
    op.execute(
        """
        UPDATE company_searches
           SET private_score = NULL,
               scoring_status = 'insufficient_data'
         WHERE rating IN ('Preliminary', 'Validation hold', 'Unrated')
        """
    )
    op.execute(
        """
        UPDATE company_reports
           SET private_score = NULL
         WHERE rating IN ('Preliminary', 'Validation hold', 'Unrated')
            OR (scoring_status IS NOT NULL AND scoring_status <> 'rated')
        """
    )
    op.execute(
        """
        UPDATE saved_companies
           SET private_score = NULL
         WHERE rating IN ('Preliminary', 'Validation hold', 'Unrated')
        """
    )


def downgrade() -> None:
    op.execute("UPDATE company_searches SET private_score = 0 WHERE private_score IS NULL")
    op.execute("UPDATE company_reports SET private_score = 0 WHERE private_score IS NULL")
    with op.batch_alter_table("company_reports") as batch:
        batch.alter_column("private_score", existing_type=sa.Integer(), nullable=False)
    with op.batch_alter_table("company_searches") as batch:
        batch.alter_column("private_score", existing_type=sa.Integer(), nullable=False)
    op.drop_column("saved_companies", "scoring_status")
    op.drop_column("company_searches", "scoring_status")

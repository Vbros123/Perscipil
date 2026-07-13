"""initial production schema

Revision ID: 20260713_0001
Revises:
Create Date: 2026-07-13
"""
from alembic import op
import sqlalchemy as sa


revision = "20260713_0001"
down_revision = None
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "users",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("email", sa.String(length=255), nullable=False),
        sa.Column("password_hash", sa.String(length=255), nullable=False),
        sa.Column("first_name", sa.String(length=120), nullable=True),
        sa.Column("last_name", sa.String(length=120), nullable=True),
        sa.Column("company", sa.String(length=180), nullable=True),
        sa.Column("role", sa.String(length=120), nullable=True),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column("email_verified", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("failed_login_count", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("locked_until", sa.DateTime(timezone=True), nullable=True),
        sa.Column("last_login_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("last_password_change_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("token_version", sa.Integer(), nullable=False, server_default="1"),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=True),
    )
    op.create_index("ix_users_email", "users", ["email"], unique=True)
    op.create_index("ix_users_id", "users", ["id"])

    op.create_table(
        "auth_audit_events",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("user_id", sa.Integer(), sa.ForeignKey("users.id", ondelete="SET NULL"), nullable=True),
        sa.Column("event_type", sa.String(length=80), nullable=False),
        sa.Column("email", sa.String(length=255), nullable=True),
        sa.Column("ip_address", sa.String(length=64), nullable=True),
        sa.Column("user_agent", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=True),
    )
    op.create_index("ix_auth_audit_events_created_at", "auth_audit_events", ["created_at"])
    op.create_index("ix_auth_audit_events_email", "auth_audit_events", ["email"])
    op.create_index("ix_auth_audit_events_event_type", "auth_audit_events", ["event_type"])
    op.create_index("ix_auth_audit_events_user_id", "auth_audit_events", ["user_id"])

    op.create_table(
        "security_tokens",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("user_id", sa.Integer(), sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False),
        sa.Column("token_type", sa.String(length=40), nullable=False),
        sa.Column("token_hash", sa.String(length=128), nullable=False),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("used_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=True),
    )
    op.create_index("ix_security_tokens_expires_at", "security_tokens", ["expires_at"])
    op.create_index("ix_security_tokens_token_hash", "security_tokens", ["token_hash"], unique=True)
    op.create_index("ix_security_tokens_token_type", "security_tokens", ["token_type"])
    op.create_index("ix_security_tokens_user_id", "security_tokens", ["user_id"])

    op.create_table(
        "user_settings",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("user_id", sa.Integer(), sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False),
        sa.Column("default_view", sa.String(length=40), nullable=False),
        sa.Column("risk_threshold", sa.Integer(), nullable=False),
        sa.Column("email_alerts", sa.Boolean(), nullable=False),
        sa.Column("weekly_digest", sa.Boolean(), nullable=False),
        sa.Column("simulated_data_labels", sa.Boolean(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=True),
    )
    op.create_index("ix_user_settings_user_id", "user_settings", ["user_id"], unique=True)

    op.create_table(
        "company_searches",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("user_id", sa.Integer(), sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=True),
        sa.Column("company_name", sa.String(length=180), nullable=False),
        sa.Column("normalized_name", sa.String(length=180), nullable=False),
        sa.Column("private_score", sa.Integer(), nullable=False),
        sa.Column("rating", sa.String(length=60), nullable=False),
        sa.Column("color", sa.String(length=20), nullable=False),
        sa.Column("query_type", sa.String(length=30), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=True),
    )
    op.create_index("ix_company_searches_company_name", "company_searches", ["company_name"])
    op.create_index("ix_company_searches_created_at", "company_searches", ["created_at"])
    op.create_index("ix_company_searches_normalized_name", "company_searches", ["normalized_name"])
    op.create_index("ix_company_searches_user_id", "company_searches", ["user_id"])

    op.create_table(
        "saved_companies",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("user_id", sa.Integer(), sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False),
        sa.Column("company_name", sa.String(length=180), nullable=False),
        sa.Column("normalized_name", sa.String(length=180), nullable=False),
        sa.Column("private_score", sa.Integer(), nullable=True),
        sa.Column("rating", sa.String(length=60), nullable=True),
        sa.Column("color", sa.String(length=20), nullable=True),
        sa.Column("notes", sa.Text(), nullable=True),
        sa.Column("tags", sa.JSON(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=True),
        sa.UniqueConstraint("user_id", "normalized_name", name="uq_saved_user_company"),
    )
    op.create_index("ix_saved_companies_user_id", "saved_companies", ["user_id"])

    op.create_table(
        "company_reports",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("user_id", sa.Integer(), sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=True),
        sa.Column("company_name", sa.String(length=180), nullable=False),
        sa.Column("normalized_name", sa.String(length=180), nullable=False),
        sa.Column("private_score", sa.Integer(), nullable=False),
        sa.Column("rating", sa.String(length=60), nullable=False),
        sa.Column("report_json", sa.JSON(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=True),
    )
    op.create_index("ix_company_reports_company_name", "company_reports", ["company_name"])
    op.create_index("ix_company_reports_created_at", "company_reports", ["created_at"])
    op.create_index("ix_company_reports_normalized_name", "company_reports", ["normalized_name"])
    op.create_index("ix_company_reports_user_id", "company_reports", ["user_id"])


def downgrade() -> None:
    op.drop_table("company_reports")
    op.drop_table("saved_companies")
    op.drop_table("company_searches")
    op.drop_table("user_settings")
    op.drop_table("security_tokens")
    op.drop_table("auth_audit_events")
    op.drop_index("ix_users_id", table_name="users")
    op.drop_index("ix_users_email", table_name="users")
    op.drop_table("users")

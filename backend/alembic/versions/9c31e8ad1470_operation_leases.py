"""Shared worker and provider capacity leases."""
from alembic import op
import sqlalchemy as sa
revision = '9c31e8ad1470'
down_revision = '8b22e091e431'
branch_labels = None
depends_on = None

def upgrade():
    op.create_table('operation_leases', sa.Column('key', sa.String(100), primary_key=True), sa.Column('token', sa.String(64), nullable=False), sa.Column('expires_at', sa.DateTime(timezone=True), nullable=False))

def downgrade():
    op.drop_table('operation_leases')

"""Deletion replay ledger independent of user foreign keys."""
from alembic import op
import sqlalchemy as sa
revision='ad421f560371'
down_revision='9c31e8ad1470'
branch_labels=None
depends_on=None

def upgrade():
    op.create_table('deletion_markers',sa.Column('key',sa.String(100),primary_key=True),sa.Column('deleted_at',sa.DateTime(timezone=True),nullable=False))

def downgrade():op.drop_table('deletion_markers')

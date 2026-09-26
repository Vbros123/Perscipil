"""Portable atomic recovery-code consumption."""
from alembic import op
import sqlalchemy as sa
revision = '8b22e091e431'
down_revision = '5da46a24aab7'
branch_labels = None
depends_on = None

def upgrade():
    op.add_column('mfa_credentials', sa.Column('recovery_version', sa.Integer(), nullable=False, server_default='0'))

def downgrade():
    with op.batch_alter_table('mfa_credentials') as batch:
        batch.drop_column('recovery_version')

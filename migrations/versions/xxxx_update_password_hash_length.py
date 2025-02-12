"""Update password_hash length

Revision ID: xxxx
Revises: yyyy
Create Date: 2025-02-11 00:00:00.000000

"""
from alembic import op
import sqlalchemy as sa

# Revision identifiers, used by Alembic.
revision = 'xxxx'
down_revision = 'yyyy'
branch_labels = None
depends_on = None

def upgrade():
    # Update the length of the password_hash column
    op.alter_column('user', 'password_hash', type_=sa.String(length=255))

def downgrade():
    # Revert the length of the password_hash column
    op.alter_column('user', 'password_hash', type_=sa.String(length=128))
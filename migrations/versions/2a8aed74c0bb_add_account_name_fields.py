"""add account name fields

Revision ID: 2a8aed74c0bb
Revises: 6a26f06e95a2
Create Date: 2026-02-21 21:10:04.569118
"""
from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision = "2a8aed74c0bb"
down_revision = "6a26f06e95a2"
branch_labels = None
depends_on = None


def upgrade():
    op.execute("ALTER TABLE accounts ADD COLUMN IF NOT EXISTS first_name VARCHAR(80)")
    op.execute("ALTER TABLE accounts ADD COLUMN IF NOT EXISTS last_name VARCHAR(80)")
    op.execute("ALTER TABLE accounts ADD COLUMN IF NOT EXISTS phone VARCHAR(30)")
    op.execute("ALTER TABLE accounts DROP COLUMN IF EXISTS name")
    op.execute("UPDATE accounts SET first_name = COALESCE(first_name, 'Unknown')")
    op.execute("UPDATE accounts SET last_name  = COALESCE(last_name,  'User')")
    op.execute("ALTER TABLE accounts ALTER COLUMN first_name SET NOT NULL")
    op.execute("ALTER TABLE accounts ALTER COLUMN last_name  SET NOT NULL")


def downgrade():
    op.execute("ALTER TABLE accounts DROP COLUMN IF EXISTS phone")
    op.execute("ALTER TABLE accounts DROP COLUMN IF EXISTS last_name")
    op.execute("ALTER TABLE accounts DROP COLUMN IF EXISTS first_name")
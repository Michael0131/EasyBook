"""add account name fields

Revision ID: 2a8aed74c0bb
Revises: 6a26f06e95a2
Create Date: 2026-02-21 21:10:04.569118

"""
from alembic import op
import sqlalchemy as sa

def upgrade():
    # Add new columns if missing
    op.execute("ALTER TABLE accounts ADD COLUMN IF NOT EXISTS first_name VARCHAR(80)")
    op.execute("ALTER TABLE accounts ADD COLUMN IF NOT EXISTS last_name VARCHAR(80)")
    op.execute("ALTER TABLE accounts ADD COLUMN IF NOT EXISTS phone VARCHAR(30)")

    # If you previously had a `name` column in some environments, drop it safely
    op.execute("ALTER TABLE accounts DROP COLUMN IF EXISTS name")

    # Make first/last NOT NULL (only after ensuring values exist)
    op.execute("UPDATE accounts SET first_name = COALESCE(first_name, 'Unknown')")
    op.execute("UPDATE accounts SET last_name  = COALESCE(last_name,  'User')")

    op.execute("ALTER TABLE accounts ALTER COLUMN first_name SET NOT NULL")
    op.execute("ALTER TABLE accounts ALTER COLUMN last_name  SET NOT NULL")


def downgrade():
    # Downgrade is optional for school projects; keep simple
    op.execute("ALTER TABLE accounts DROP COLUMN IF EXISTS phone")
    op.execute("ALTER TABLE accounts DROP COLUMN IF EXISTS last_name")
    op.execute("ALTER TABLE accounts DROP COLUMN IF EXISTS first_name")

"""Identifier les sessions publiques de démonstration.

Revision ID: 0015_demo_sessions
Revises: 0014_simple_admin_signup
"""
from alembic import op
import sqlalchemy as sa

revision = '0015_demo_sessions'
down_revision = '0014_simple_admin_signup'
branch_labels = None
depends_on = None


def upgrade():
    op.add_column('user_sessions', sa.Column(
        'is_demo', sa.Boolean(), nullable=False, server_default=sa.false()))


def downgrade():
    op.drop_column('user_sessions', 'is_demo')

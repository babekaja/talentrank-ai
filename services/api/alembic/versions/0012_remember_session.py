"""Remember-me preference for persistent browser sessions.

Revision ID: 0012_remember_session
Revises: 0011_candidate_portal
"""
from alembic import op
import sqlalchemy as sa


revision = '0012_remember_session'
down_revision = '0011_candidate_portal'
branch_labels = None
depends_on = None


def upgrade():
    op.add_column('user_sessions', sa.Column(
        'remember_me', sa.Boolean(), nullable=False, server_default=sa.false()))


def downgrade():
    op.drop_column('user_sessions', 'remember_me')

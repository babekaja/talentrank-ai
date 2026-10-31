"""Création directe du compte administrateur, sans confirmation email.

Revision ID: 0014_simple_admin_signup
Revises: 0013_account_email_verification
"""
from alembic import op
import sqlalchemy as sa

revision = '0014_simple_admin_signup'
down_revision = '0013_account_email_verification'
branch_labels = None
depends_on = None


def upgrade():
    op.drop_table('account_email_verifications')


def downgrade():
    op.create_table('account_email_verifications',
        sa.Column('id', sa.String(36), primary_key=True),
        sa.Column('user_id', sa.String(36), sa.ForeignKey('users.id', ondelete='CASCADE'), nullable=False, unique=True),
        sa.Column('organization_id', sa.String(36), sa.ForeignKey('organizations.id', ondelete='CASCADE'), nullable=False),
        sa.Column('token_hash', sa.String(64), nullable=False, unique=True),
        sa.Column('expires_at', sa.DateTime(), nullable=False),
        sa.Column('sent_at', sa.DateTime(), nullable=False),
        sa.Column('verified_at', sa.DateTime()),
        sa.Column('created_at', sa.DateTime(), nullable=False))

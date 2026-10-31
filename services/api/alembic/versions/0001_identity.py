"""Phase 1: tenants, users, memberships, revocable sessions.

Revision ID: 0001_identity
Revises:
"""
from alembic import op
import sqlalchemy as sa

revision = '0001_identity'
down_revision = None
branch_labels = None
depends_on = None


def upgrade():
    op.create_table('organizations',
        sa.Column('id', sa.String(36), primary_key=True),
        sa.Column('name', sa.String(180), nullable=False),
        sa.Column('slug', sa.String(80), nullable=False, unique=True),
        sa.Column('is_active', sa.Boolean(), nullable=False),
        sa.Column('created_at', sa.DateTime(), nullable=False))
    op.create_table('users',
        sa.Column('id', sa.String(36), primary_key=True),
        sa.Column('email', sa.String(254), nullable=False, unique=True),
        sa.Column('full_name', sa.String(180), nullable=False),
        sa.Column('password_hash', sa.String(255), nullable=False),
        sa.Column('is_active', sa.Boolean(), nullable=False),
        sa.Column('created_at', sa.DateTime(), nullable=False))
    op.create_table('organization_members',
        sa.Column('id', sa.String(36), primary_key=True),
        sa.Column('organization_id', sa.String(36), sa.ForeignKey('organizations.id', ondelete='CASCADE'), nullable=False),
        sa.Column('user_id', sa.String(36), sa.ForeignKey('users.id', ondelete='CASCADE'), nullable=False),
        sa.Column('role', sa.String(25), nullable=False),
        sa.Column('is_active', sa.Boolean(), nullable=False),
        sa.UniqueConstraint('organization_id', 'user_id', name='uq_org_member'))
    op.create_index('ix_organization_members_organization_id', 'organization_members', ['organization_id'])
    op.create_index('ix_organization_members_user_id', 'organization_members', ['user_id'])
    op.create_table('user_sessions',
        sa.Column('id', sa.String(36), primary_key=True),
        sa.Column('user_id', sa.String(36), sa.ForeignKey('users.id', ondelete='CASCADE'), nullable=False),
        sa.Column('organization_id', sa.String(36), sa.ForeignKey('organizations.id', ondelete='CASCADE'), nullable=False),
        sa.Column('refresh_hash', sa.String(64), nullable=False, unique=True),
        sa.Column('expires_at', sa.DateTime(), nullable=False),
        sa.Column('created_at', sa.DateTime(), nullable=False),
        sa.Column('revoked_at', sa.DateTime(), nullable=True))
    op.create_index('ix_sessions_user_org', 'user_sessions', ['user_id', 'organization_id'])


def downgrade():
    op.drop_table('user_sessions')
    op.drop_table('organization_members')
    op.drop_table('users')
    op.drop_table('organizations')

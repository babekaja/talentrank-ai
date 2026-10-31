"""Retention configuration and legal holds, phase 7.

Revision ID: 0007_privacy
Revises: 0006_reports
"""
from alembic import op
import sqlalchemy as sa

revision = '0007_privacy'
down_revision = '0006_reports'
branch_labels = None
depends_on = None


def upgrade():
    op.create_table('retention_policies',
        sa.Column('organization_id', sa.String(36), sa.ForeignKey('organizations.id', ondelete='CASCADE'), primary_key=True),
        sa.Column('retention_days', sa.Integer(), nullable=False),
        sa.Column('updated_by', sa.String(36), sa.ForeignKey('users.id'), nullable=False),
        sa.Column('updated_at', sa.DateTime(), nullable=False))
    op.create_table('candidate_legal_holds',
        sa.Column('candidate_id', sa.String(36), sa.ForeignKey('candidates.id', ondelete='CASCADE'), primary_key=True),
        sa.Column('organization_id', sa.String(36), sa.ForeignKey('organizations.id', ondelete='CASCADE'), nullable=False),
        sa.Column('active', sa.Boolean(), nullable=False),
        sa.Column('reason', sa.Text(), nullable=False),
        sa.Column('updated_by', sa.String(36), sa.ForeignKey('users.id'), nullable=False),
        sa.Column('updated_at', sa.DateTime(), nullable=False))
    op.create_index('ix_hold_org_active', 'candidate_legal_holds', ['organization_id', 'active'])


def downgrade():
    op.drop_index('ix_hold_org_active', table_name='candidate_legal_holds')
    op.drop_table('candidate_legal_holds')
    op.drop_table('retention_policies')

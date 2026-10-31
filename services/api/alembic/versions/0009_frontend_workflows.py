"""Evaluator assignments and organization training catalog.

Revision ID: 0009_frontend_workflows
Revises: 0008_ml_evidence
"""
from alembic import op
import sqlalchemy as sa

revision = '0009_frontend_workflows'
down_revision = '0008_ml_evidence'
branch_labels = None
depends_on = None


def upgrade():
    op.create_table('application_assignments',
        sa.Column('id', sa.String(36), primary_key=True),
        sa.Column('organization_id', sa.String(36), sa.ForeignKey('organizations.id', ondelete='CASCADE'), nullable=False),
        sa.Column('application_id', sa.String(36), sa.ForeignKey('applications.id', ondelete='CASCADE'), nullable=False),
        sa.Column('evaluator_member_id', sa.String(36), sa.ForeignKey('organization_members.id'), nullable=False),
        sa.Column('assigned_by', sa.String(36), sa.ForeignKey('users.id'), nullable=False),
        sa.Column('status', sa.String(20), nullable=False),
        sa.Column('created_at', sa.DateTime(), nullable=False),
        sa.Column('completed_at', sa.DateTime()),
        sa.Column('revoked_at', sa.DateTime()),
        sa.UniqueConstraint('application_id', 'evaluator_member_id', name='uq_assignment_application_member'))
    op.create_index('ix_assignment_org_member_state', 'application_assignments',
                    ['organization_id', 'evaluator_member_id', 'status'])
    op.create_table('training_courses',
        sa.Column('id', sa.String(36), primary_key=True),
        sa.Column('organization_id', sa.String(36), sa.ForeignKey('organizations.id', ondelete='CASCADE'), nullable=False),
        sa.Column('title', sa.String(220), nullable=False),
        sa.Column('provider', sa.String(180), nullable=False),
        sa.Column('official_url', sa.String(2000), nullable=False),
        sa.Column('language', sa.String(15), nullable=False),
        sa.Column('level', sa.String(30), nullable=False),
        sa.Column('skill_id', sa.String(36), sa.ForeignKey('skills.id')),
        sa.Column('description', sa.Text(), nullable=False),
        sa.Column('is_active', sa.Boolean(), nullable=False),
        sa.Column('verified_at', sa.DateTime()),
        sa.Column('verified_by', sa.String(36), sa.ForeignKey('users.id')),
        sa.Column('created_at', sa.DateTime(), nullable=False),
        sa.Column('updated_at', sa.DateTime(), nullable=False))
    op.create_index('ix_course_org_active', 'training_courses', ['organization_id', 'is_active'])


def downgrade():
    op.drop_index('ix_course_org_active', table_name='training_courses')
    op.drop_table('training_courses')
    op.drop_index('ix_assignment_org_member_state', table_name='application_assignments')
    op.drop_table('application_assignments')

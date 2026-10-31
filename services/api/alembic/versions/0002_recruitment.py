"""Phase 2: recruitment core. Frozen explicit Alembic operations.

Revision ID: 0002_recruitment
Revises: 0001_identity
"""
from alembic import op
import sqlalchemy as sa

revision = '0002_recruitment'
down_revision = '0001_identity'
branch_labels = None
depends_on = None

def upgrade():
        op.create_table('audit_logs',
        sa.Column('id', sa.String(length=36), nullable=False),
        sa.Column('organization_id', sa.String(length=36), nullable=False),
        sa.Column('actor_id', sa.String(length=36), nullable=False),
        sa.Column('action', sa.String(length=100), nullable=False),
        sa.Column('resource_type', sa.String(length=60), nullable=False),
        sa.Column('resource_id', sa.String(length=36), nullable=False),
        sa.Column('details', sa.JSON(), nullable=False),
        sa.Column('created_at', sa.DateTime(), nullable=False),
        sa.ForeignKeyConstraint(['actor_id'], ['users.id'], ),
        sa.ForeignKeyConstraint(['organization_id'], ['organizations.id'], ),
        sa.PrimaryKeyConstraint('id')
        )
        op.create_index('ix_audit_org_date', 'audit_logs', ['organization_id', 'created_at'], unique=False)
        op.create_table('candidates',
        sa.Column('id', sa.String(length=36), nullable=False),
        sa.Column('organization_id', sa.String(length=36), nullable=False),
        sa.Column('reference', sa.String(length=60), nullable=False),
        sa.Column('full_name', sa.String(length=180), nullable=False),
        sa.Column('created_at', sa.DateTime(), nullable=False),
        sa.ForeignKeyConstraint(['organization_id'], ['organizations.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id')
        )
        op.create_index('ix_candidate_org_created', 'candidates', ['organization_id', 'created_at'], unique=False)
        op.create_index(op.f('ix_candidates_organization_id'), 'candidates', ['organization_id'], unique=False)
        op.create_table('invitations',
        sa.Column('id', sa.String(length=36), nullable=False),
        sa.Column('organization_id', sa.String(length=36), nullable=False),
        sa.Column('email', sa.String(length=254), nullable=False),
        sa.Column('role', sa.String(length=25), nullable=False),
        sa.Column('token_hash', sa.String(length=64), nullable=False),
        sa.Column('expires_at', sa.DateTime(), nullable=False),
        sa.Column('accepted_at', sa.DateTime(), nullable=True),
        sa.Column('revoked_at', sa.DateTime(), nullable=True),
        sa.Column('created_by', sa.String(length=36), nullable=False),
        sa.Column('created_at', sa.DateTime(), nullable=False),
        sa.ForeignKeyConstraint(['created_by'], ['users.id'], ),
        sa.ForeignKeyConstraint(['organization_id'], ['organizations.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('token_hash')
        )
        op.create_index('ix_invitation_org_email', 'invitations', ['organization_id', 'email'], unique=False)
        op.create_table('jobs',
        sa.Column('id', sa.String(length=36), nullable=False),
        sa.Column('organization_id', sa.String(length=36), nullable=False),
        sa.Column('title', sa.String(length=180), nullable=False),
        sa.Column('department', sa.String(length=120), nullable=True),
        sa.Column('location', sa.String(length=180), nullable=True),
        sa.Column('contract_type', sa.String(length=60), nullable=True),
        sa.Column('work_mode', sa.String(length=30), nullable=True),
        sa.Column('description', sa.Text(), nullable=False),
        sa.Column('status', sa.String(length=20), nullable=False),
        sa.Column('opens_on', sa.Date(), nullable=True),
        sa.Column('closes_on', sa.Date(), nullable=True),
        sa.Column('criteria_version', sa.Integer(), nullable=False),
        sa.Column('criteria_confirmed_at', sa.DateTime(), nullable=True),
        sa.Column('criteria_confirmed_by', sa.String(length=36), nullable=True),
        sa.Column('created_by', sa.String(length=36), nullable=False),
        sa.Column('created_at', sa.DateTime(), nullable=False),
        sa.Column('updated_at', sa.DateTime(), nullable=False),
        sa.ForeignKeyConstraint(['created_by'], ['users.id'], ),
        sa.ForeignKeyConstraint(['criteria_confirmed_by'], ['users.id'], ),
        sa.ForeignKeyConstraint(['organization_id'], ['organizations.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id')
        )
        op.create_index('ix_job_org_state', 'jobs', ['organization_id', 'status'], unique=False)
        op.create_index(op.f('ix_jobs_organization_id'), 'jobs', ['organization_id'], unique=False)
        op.create_table('candidate_contacts',
        sa.Column('candidate_id', sa.String(length=36), nullable=False),
        sa.Column('email', sa.String(length=254), nullable=True),
        sa.Column('phone', sa.String(length=50), nullable=True),
        sa.ForeignKeyConstraint(['candidate_id'], ['candidates.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('candidate_id')
        )
        op.create_table('job_requirements',
        sa.Column('id', sa.String(length=36), nullable=False),
        sa.Column('job_id', sa.String(length=36), nullable=False),
        sa.Column('code', sa.String(length=50), nullable=False),
        sa.Column('label', sa.String(length=160), nullable=False),
        sa.Column('category', sa.String(length=30), nullable=False),
        sa.Column('required', sa.Boolean(), nullable=False),
        sa.Column('weight', sa.Integer(), nullable=False),
        sa.Column('justification', sa.Text(), nullable=False),
        sa.Column('skill_ref', sa.String(length=120), nullable=True),
        sa.Column('created_at', sa.DateTime(), nullable=False),
        sa.ForeignKeyConstraint(['job_id'], ['jobs.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('job_id', 'code', name='uq_job_requirement_code')
        )
        op.create_index(op.f('ix_job_requirements_job_id'), 'job_requirements', ['job_id'], unique=False)
        op.create_table('recruitment_campaigns',
        sa.Column('id', sa.String(length=36), nullable=False),
        sa.Column('organization_id', sa.String(length=36), nullable=False),
        sa.Column('job_id', sa.String(length=36), nullable=False),
        sa.Column('name', sa.String(length=180), nullable=False),
        sa.Column('status', sa.String(length=20), nullable=False),
        sa.Column('created_by', sa.String(length=36), nullable=False),
        sa.Column('created_at', sa.DateTime(), nullable=False),
        sa.ForeignKeyConstraint(['created_by'], ['users.id'], ),
        sa.ForeignKeyConstraint(['job_id'], ['jobs.id'], ),
        sa.ForeignKeyConstraint(['organization_id'], ['organizations.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id')
        )
        op.create_index('ix_campaign_org_status', 'recruitment_campaigns', ['organization_id', 'status'], unique=False)
        op.create_index(op.f('ix_recruitment_campaigns_job_id'), 'recruitment_campaigns', ['job_id'], unique=False)
        op.create_index(op.f('ix_recruitment_campaigns_organization_id'), 'recruitment_campaigns', ['organization_id'], unique=False)
        op.create_table('applications',
        sa.Column('id', sa.String(length=36), nullable=False),
        sa.Column('organization_id', sa.String(length=36), nullable=False),
        sa.Column('campaign_id', sa.String(length=36), nullable=False),
        sa.Column('candidate_id', sa.String(length=36), nullable=False),
        sa.Column('review_status', sa.String(length=24), nullable=False),
        sa.Column('created_at', sa.DateTime(), nullable=False),
        sa.ForeignKeyConstraint(['campaign_id'], ['recruitment_campaigns.id'], ),
        sa.ForeignKeyConstraint(['candidate_id'], ['candidates.id'], ),
        sa.ForeignKeyConstraint(['organization_id'], ['organizations.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('campaign_id', 'candidate_id', name='uq_application_campaign_candidate')
        )
        op.create_index('ix_application_org_state', 'applications', ['organization_id', 'review_status'], unique=False)
        op.create_index(op.f('ix_applications_campaign_id'), 'applications', ['campaign_id'], unique=False)
        op.create_index(op.f('ix_applications_candidate_id'), 'applications', ['candidate_id'], unique=False)
        op.create_index(op.f('ix_applications_organization_id'), 'applications', ['organization_id'], unique=False)
        op.create_table('application_reviews',
        sa.Column('id', sa.String(length=36), nullable=False),
        sa.Column('application_id', sa.String(length=36), nullable=False),
        sa.Column('author_id', sa.String(length=36), nullable=False),
        sa.Column('finding', sa.String(length=24), nullable=False),
        sa.Column('note', sa.Text(), nullable=False),
        sa.Column('created_at', sa.DateTime(), nullable=False),
        sa.ForeignKeyConstraint(['application_id'], ['applications.id'], ),
        sa.ForeignKeyConstraint(['author_id'], ['users.id'], ),
        sa.PrimaryKeyConstraint('id')
        )
        op.create_index(op.f('ix_application_reviews_application_id'), 'application_reviews', ['application_id'], unique=False)

def downgrade():
        op.drop_index(op.f('ix_application_reviews_application_id'), table_name='application_reviews')
        op.drop_table('application_reviews')
        op.drop_index(op.f('ix_applications_organization_id'), table_name='applications')
        op.drop_index(op.f('ix_applications_candidate_id'), table_name='applications')
        op.drop_index(op.f('ix_applications_campaign_id'), table_name='applications')
        op.drop_index('ix_application_org_state', table_name='applications')
        op.drop_table('applications')
        op.drop_index(op.f('ix_recruitment_campaigns_organization_id'), table_name='recruitment_campaigns')
        op.drop_index(op.f('ix_recruitment_campaigns_job_id'), table_name='recruitment_campaigns')
        op.drop_index('ix_campaign_org_status', table_name='recruitment_campaigns')
        op.drop_table('recruitment_campaigns')
        op.drop_index(op.f('ix_job_requirements_job_id'), table_name='job_requirements')
        op.drop_table('job_requirements')
        op.drop_table('candidate_contacts')
        op.drop_index(op.f('ix_jobs_organization_id'), table_name='jobs')
        op.drop_index('ix_job_org_state', table_name='jobs')
        op.drop_table('jobs')
        op.drop_index('ix_invitation_org_email', table_name='invitations')
        op.drop_table('invitations')
        op.drop_index(op.f('ix_candidates_organization_id'), table_name='candidates')
        op.drop_index('ix_candidate_org_created', table_name='candidates')
        op.drop_table('candidates')
        op.drop_index('ix_audit_org_date', table_name='audit_logs')
        op.drop_table('audit_logs')

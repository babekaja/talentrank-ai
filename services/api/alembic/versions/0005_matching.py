"""Phase 5 matching: fixed schema operations; no model imports at upgrade time.

Revision ID: 0005_matching
Revises: 0004_nlp
"""
from alembic import op
import sqlalchemy as sa

revision = '0005_matching'
down_revision = '0004_nlp'
branch_labels = None
depends_on = None


def upgrade():
    op.create_table('matching_configurations',
        sa.Column('id', sa.String(36), nullable=False, primary_key=True),
        sa.Column('organization_id', sa.String(36), sa.ForeignKey('organizations.id', ondelete='CASCADE'), nullable=False, primary_key=False),
        sa.Column('version', sa.Integer(), nullable=False, primary_key=False),
        sa.Column('weights', sa.JSON(), nullable=False, primary_key=False),
        sa.Column('created_by', sa.String(36), sa.ForeignKey('users.id'), nullable=False, primary_key=False),
        sa.Column('created_at', sa.DateTime(), nullable=False, primary_key=False),
        sa.UniqueConstraint('organization_id', 'version', name='uq_matching_config_version'),
    )
    op.create_index('ix_matching_configurations_organization_id', 'matching_configurations', ['organization_id'])
    op.create_table('matching_runs',
        sa.Column('id', sa.String(36), nullable=False, primary_key=True),
        sa.Column('organization_id', sa.String(36), sa.ForeignKey('organizations.id', ondelete='CASCADE'), nullable=False, primary_key=False),
        sa.Column('campaign_id', sa.String(36), sa.ForeignKey('recruitment_campaigns.id'), nullable=False, primary_key=False),
        sa.Column('job_id', sa.String(36), sa.ForeignKey('jobs.id'), nullable=False, primary_key=False),
        sa.Column('criteria_version', sa.Integer(), nullable=False, primary_key=False),
        sa.Column('config_version', sa.Integer(), nullable=False, primary_key=False),
        sa.Column('algorithm_version', sa.String(50), nullable=False, primary_key=False),
        sa.Column('weights_snapshot', sa.JSON(), nullable=False, primary_key=False),
        sa.Column('requirements_snapshot', sa.JSON(), nullable=False, primary_key=False),
        sa.Column('application_ids_snapshot', sa.JSON(), nullable=False, primary_key=False),
        sa.Column('skill_mapping_snapshot', sa.JSON(), nullable=False, primary_key=False),
        sa.Column('status', sa.String(25), nullable=False, primary_key=False),
        sa.Column('total', sa.Integer(), nullable=False, primary_key=False),
        sa.Column('processed', sa.Integer(), nullable=False, primary_key=False),
        sa.Column('error_code', sa.String(80), nullable=True, primary_key=False),
        sa.Column('created_by', sa.String(36), sa.ForeignKey('users.id'), nullable=False, primary_key=False),
        sa.Column('created_at', sa.DateTime(), nullable=False, primary_key=False),
        sa.Column('completed_at', sa.DateTime(), nullable=True, primary_key=False),
    )
    op.create_index('ix_matching_run_org_campaign', 'matching_runs', ['organization_id', 'campaign_id'])
    op.create_table('matching_results',
        sa.Column('id', sa.String(36), nullable=False, primary_key=True),
        sa.Column('run_id', sa.String(36), sa.ForeignKey('matching_runs.id', ondelete='CASCADE'), nullable=False, primary_key=False),
        sa.Column('application_id', sa.String(36), sa.ForeignKey('applications.id'), nullable=False, primary_key=False),
        sa.Column('candidate_id', sa.String(36), sa.ForeignKey('candidates.id'), nullable=False, primary_key=False),
        sa.Column('score', sa.Numeric(6, 2), nullable=True, primary_key=False),
        sa.Column('state', sa.String(35), nullable=False, primary_key=False),
        sa.Column('documented', sa.Integer(), nullable=False, primary_key=False),
        sa.Column('to_review', sa.Integer(), nullable=False, primary_key=False),
        sa.Column('not_documented', sa.Integer(), nullable=False, primary_key=False),
        sa.Column('evidence_fingerprint', sa.String(64), nullable=False, primary_key=False),
        sa.Column('group_coverage', sa.JSON(), nullable=False, primary_key=False),
        sa.Column('created_at', sa.DateTime(), nullable=False, primary_key=False),
        sa.UniqueConstraint('run_id', 'application_id', name='uq_matching_run_application'),
    )
    op.create_index('ix_matching_result_run_score', 'matching_results', ['run_id', 'score'])
    op.create_table('matching_criteria_results',
        sa.Column('id', sa.String(36), nullable=False, primary_key=True),
        sa.Column('result_id', sa.String(36), sa.ForeignKey('matching_results.id', ondelete='CASCADE'), nullable=False, primary_key=False),
        sa.Column('requirement_id', sa.String(36), nullable=False, primary_key=False),
        sa.Column('code', sa.String(50), nullable=False, primary_key=False),
        sa.Column('label', sa.String(160), nullable=False, primary_key=False),
        sa.Column('group_code', sa.String(32), nullable=False, primary_key=False),
        sa.Column('state', sa.String(35), nullable=False, primary_key=False),
        sa.Column('weight', sa.Integer(), nullable=False, primary_key=False),
        sa.Column('contribution', sa.Numeric(8, 4), nullable=False, primary_key=False),
        sa.Column('note_code', sa.String(60), nullable=False, primary_key=False),
        sa.UniqueConstraint('result_id', 'requirement_id', name='uq_matching_result_criterion'),
    )
    op.create_index('ix_matching_criteria_results_result_id', 'matching_criteria_results', ['result_id'])
    op.create_table('matching_evidence',
        sa.Column('id', sa.String(36), nullable=False, primary_key=True),
        sa.Column('criterion_result_id', sa.String(36), sa.ForeignKey('matching_criteria_results.id', ondelete='CASCADE'), nullable=False, primary_key=False),
        sa.Column('evidence_id', sa.String(36), sa.ForeignKey('skill_evidence.id', ondelete='SET NULL'), nullable=True, primary_key=False),
        sa.Column('document_id', sa.String(36), sa.ForeignKey('cv_documents.id', ondelete='CASCADE'), nullable=False, primary_key=False),
        sa.Column('page_id', sa.String(36), sa.ForeignKey('document_pages.id', ondelete='CASCADE'), nullable=False, primary_key=False),
        sa.Column('page_number', sa.Integer(), nullable=False, primary_key=False),
        sa.Column('start_offset', sa.Integer(), nullable=False, primary_key=False),
        sa.Column('end_offset', sa.Integer(), nullable=False, primary_key=False),
        sa.Column('matched_text', sa.String(190), nullable=False, primary_key=False),
        sa.Column('verification_status', sa.String(25), nullable=False, primary_key=False),
    )
    op.create_index('ix_matching_evidence_criterion_result_id', 'matching_evidence', ['criterion_result_id'])


def downgrade():
    op.drop_index('ix_matching_evidence_criterion_result_id', table_name='matching_evidence')
    op.drop_table('matching_evidence')
    op.drop_index('ix_matching_criteria_results_result_id', table_name='matching_criteria_results')
    op.drop_table('matching_criteria_results')
    op.drop_index('ix_matching_result_run_score', table_name='matching_results')
    op.drop_table('matching_results')
    op.drop_index('ix_matching_run_org_campaign', table_name='matching_runs')
    op.drop_table('matching_runs')
    op.drop_index('ix_matching_configurations_organization_id', table_name='matching_configurations')
    op.drop_table('matching_configurations')

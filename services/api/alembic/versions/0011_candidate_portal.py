"""Candidate email ownership and consent records.
Revision ID: 0011_candidate_portal
Revises: 0010_africa_skills
"""
from alembic import op
import sqlalchemy as sa
revision = '0011_candidate_portal'
down_revision = '0010_africa_skills'
branch_labels = None
depends_on = None


def upgrade():
    op.create_table('candidate_portal_tokens',
        sa.Column('id', sa.String(36), primary_key=True),
        sa.Column('candidate_id', sa.String(36), sa.ForeignKey('candidates.id', ondelete='CASCADE'), nullable=False),
        sa.Column('organization_id', sa.String(36), sa.ForeignKey('organizations.id', ondelete='CASCADE'), nullable=False),
        sa.Column('email_fingerprint', sa.String(64), nullable=False),
        sa.Column('challenge_hash', sa.String(64), nullable=False, unique=True),
        sa.Column('expires_at', sa.DateTime(), nullable=False),
        sa.Column('used_at', sa.DateTime()),
        sa.Column('revoked_at', sa.DateTime()),
        sa.Column('created_at', sa.DateTime(), nullable=False))
    op.create_index('ix_portal_candidate_created', 'candidate_portal_tokens', ['candidate_id','created_at'])
    op.create_table('candidate_portal_sessions',
        sa.Column('id', sa.String(36), primary_key=True),
        sa.Column('candidate_id', sa.String(36), sa.ForeignKey('candidates.id', ondelete='CASCADE'), nullable=False),
        sa.Column('organization_id', sa.String(36), sa.ForeignKey('organizations.id', ondelete='CASCADE'), nullable=False),
        sa.Column('access_hash', sa.String(64), nullable=False, unique=True),
        sa.Column('expires_at', sa.DateTime(), nullable=False),
        sa.Column('revoked_at', sa.DateTime()),
        sa.Column('created_at', sa.DateTime(), nullable=False))
    op.create_index('ix_candidate_portal_sessions_candidate_id', 'candidate_portal_sessions', ['candidate_id'])
    op.create_table('candidate_consent_events',
        sa.Column('id', sa.String(36), primary_key=True),
        sa.Column('candidate_id', sa.String(36), sa.ForeignKey('candidates.id', ondelete='CASCADE'), nullable=False),
        sa.Column('organization_id', sa.String(36), sa.ForeignKey('organizations.id', ondelete='CASCADE'), nullable=False),
        sa.Column('purpose', sa.String(60), nullable=False),
        sa.Column('action', sa.String(20), nullable=False),
        sa.Column('notice_version', sa.String(40), nullable=False),
        sa.Column('source', sa.String(40), nullable=False),
        sa.Column('created_at', sa.DateTime(), nullable=False))
    op.create_index('ix_candidate_consent_events_candidate_id', 'candidate_consent_events', ['candidate_id'])


def downgrade():
    op.drop_index('ix_candidate_consent_events_candidate_id', table_name='candidate_consent_events')
    op.drop_table('candidate_consent_events')
    op.drop_index('ix_candidate_portal_sessions_candidate_id', table_name='candidate_portal_sessions')
    op.drop_table('candidate_portal_sessions')
    op.drop_index('ix_portal_candidate_created', table_name='candidate_portal_tokens')
    op.drop_table('candidate_portal_tokens')

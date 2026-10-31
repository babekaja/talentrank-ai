"""Context evidence and strictly source-grounded professional lines.

Revision ID: 0008_ml_evidence
Revises: 0007_privacy
"""
from alembic import op
import sqlalchemy as sa
revision = '0008_ml_evidence'
down_revision = '0007_privacy'
branch_labels = None
depends_on = None


def upgrade():
    op.add_column('skill_evidence', sa.Column('context_code', sa.String(40),
                  nullable=False, server_default='lexical_observation_only'))
    op.create_table('document_facts',
        sa.Column('id', sa.String(36), primary_key=True),
        sa.Column('organization_id', sa.String(36), sa.ForeignKey('organizations.id', ondelete='CASCADE'), nullable=False),
        sa.Column('document_id', sa.String(36), sa.ForeignKey('cv_documents.id', ondelete='CASCADE'), nullable=False),
        sa.Column('page_id', sa.String(36), sa.ForeignKey('document_pages.id', ondelete='CASCADE'), nullable=False),
        sa.Column('category', sa.String(25), nullable=False),
        sa.Column('start_offset', sa.Integer(), nullable=False),
        sa.Column('end_offset', sa.Integer(), nullable=False),
        sa.Column('source_text', sa.String(350), nullable=False),
        sa.Column('rule_version', sa.String(40), nullable=False),
        sa.Column('review_status', sa.String(25), nullable=False),
        sa.UniqueConstraint('page_id','start_offset','end_offset','category',name='uq_document_fact_span'))
    op.create_index('ix_document_facts_org_doc', 'document_facts', ['organization_id','document_id'])


def downgrade():
    op.drop_index('ix_document_facts_org_doc', table_name='document_facts')
    op.drop_table('document_facts')
    op.drop_column('skill_evidence', 'context_code')

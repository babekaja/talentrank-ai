"""Curated NLP glossary and source-anchored skill mentions.
Revision ID: 0004_nlp
Revises: 0003_documents
"""
from alembic import op
import sqlalchemy as sa
revision='0004_nlp'
down_revision='0003_documents'
branch_labels=None
depends_on=None

def upgrade():
    op.create_table('skills',
        sa.Column('id',sa.String(36),primary_key=True),
        sa.Column('code',sa.String(100),nullable=False,unique=True),
        sa.Column('label_fr',sa.String(180),nullable=False),
        sa.Column('label_en',sa.String(180),nullable=False),
        sa.Column('taxonomy',sa.String(30),nullable=False),
        sa.Column('external_uri',sa.String(255),unique=True),
        sa.Column('version',sa.String(40),nullable=False),
        sa.Column('active',sa.Boolean(),nullable=False))
    op.create_table('skill_aliases',
        sa.Column('id',sa.String(36),primary_key=True),
        sa.Column('skill_id',sa.String(36),sa.ForeignKey('skills.id',ondelete='CASCADE'),nullable=False),
        sa.Column('normalized_alias',sa.String(190),nullable=False),
        sa.Column('language',sa.String(5),nullable=False),
        sa.Column('provenance',sa.String(40),nullable=False),
        sa.Column('verified',sa.Boolean(),nullable=False),
        sa.UniqueConstraint('skill_id','normalized_alias',name='uq_skill_alias'))
    op.create_index('ix_skill_aliases_skill_id','skill_aliases',['skill_id'])
    op.create_table('organization_skill_aliases',
        sa.Column('id',sa.String(36),primary_key=True),
        sa.Column('organization_id',sa.String(36),sa.ForeignKey('organizations.id',ondelete='CASCADE'),nullable=False),
        sa.Column('skill_id',sa.String(36),sa.ForeignKey('skills.id',ondelete='CASCADE'),nullable=False),
        sa.Column('normalized_alias',sa.String(190),nullable=False),
        sa.Column('language',sa.String(5),nullable=False),
        sa.Column('justification',sa.String(400),nullable=False),
        sa.Column('reviewed_by',sa.String(36),sa.ForeignKey('users.id'),nullable=False),
        sa.Column('reviewed_at',sa.DateTime(),nullable=False),
        sa.Column('version',sa.Integer(),nullable=False),
        sa.UniqueConstraint('organization_id','skill_id','normalized_alias',name='uq_org_skill_alias'))
    op.create_index('ix_org_alias_org','organization_skill_aliases',['organization_id'])
    op.create_table('document_nlp_runs',
        sa.Column('id',sa.String(36),primary_key=True),
        sa.Column('organization_id',sa.String(36),sa.ForeignKey('organizations.id',ondelete='CASCADE'),nullable=False),
        sa.Column('document_id',sa.String(36),sa.ForeignKey('cv_documents.id',ondelete='CASCADE'),nullable=False),
        sa.Column('status',sa.String(25),nullable=False),
        sa.Column('rules_version',sa.String(40),nullable=False),
        sa.Column('taxonomy_fingerprint',sa.String(64),nullable=False),
        sa.Column('content_fingerprint',sa.String(64),nullable=False),
        sa.Column('processed_at',sa.DateTime()),
        sa.Column('error_code',sa.String(60)),
        sa.UniqueConstraint('document_id',name='uq_document_nlp_run'))
    op.create_index('ix_nlp_runs_org_state','document_nlp_runs',['organization_id','status'])
    op.create_table('skill_evidence',
        sa.Column('id',sa.String(36),primary_key=True),
        sa.Column('organization_id',sa.String(36),sa.ForeignKey('organizations.id',ondelete='CASCADE'),nullable=False),
        sa.Column('document_id',sa.String(36),sa.ForeignKey('cv_documents.id',ondelete='CASCADE'),nullable=False),
        sa.Column('page_id',sa.String(36),sa.ForeignKey('document_pages.id',ondelete='CASCADE'),nullable=False),
        sa.Column('skill_id',sa.String(36),sa.ForeignKey('skills.id'),nullable=False),
        sa.Column('start_offset',sa.Integer(),nullable=False),
        sa.Column('end_offset',sa.Integer(),nullable=False),
        sa.Column('matched_text',sa.String(190),nullable=False),
        sa.Column('match_method',sa.String(25),nullable=False),
        sa.Column('status',sa.String(25),nullable=False),
        sa.Column('rules_version',sa.String(40),nullable=False),
        sa.Column('created_at',sa.DateTime(),nullable=False),
        sa.Column('reviewed_by',sa.String(36),sa.ForeignKey('users.id')),
        sa.Column('reviewed_at',sa.DateTime()),
        sa.UniqueConstraint('document_id','page_id','start_offset','end_offset','skill_id',name='uq_evidence_span_skill'))
    op.create_index('ix_evidence_org_doc','skill_evidence',['organization_id','document_id'])
    op.create_index('ix_evidence_org_skill','skill_evidence',['organization_id','skill_id'])

def downgrade():
    op.drop_index('ix_evidence_org_skill',table_name='skill_evidence')
    op.drop_index('ix_evidence_org_doc',table_name='skill_evidence')
    op.drop_table('skill_evidence')
    op.drop_index('ix_nlp_runs_org_state',table_name='document_nlp_runs')
    op.drop_table('document_nlp_runs')
    op.drop_index('ix_skill_aliases_skill_id',table_name='skill_aliases')
    op.drop_table('skill_aliases')
    op.drop_index('ix_org_alias_org',table_name='organization_skill_aliases')
    op.drop_table('organization_skill_aliases')
    op.drop_table('skills')

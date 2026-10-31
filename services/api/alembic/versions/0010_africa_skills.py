"""Tenant-scoped African skills graph + recorded candidate preferences.
Revision ID: 0010_africa_skills
Revises: 0009_frontend_workflows
"""
from alembic import op
import sqlalchemy as sa
revision='0010_africa_skills'
down_revision='0009_frontend_workflows'
branch_labels=None
depends_on=None

def upgrade():
    op.create_table('africa_skill_relations',
        sa.Column('id',sa.String(36),primary_key=True),
        sa.Column('organization_id',sa.String(36),sa.ForeignKey('organizations.id',ondelete='CASCADE'),nullable=False),
        sa.Column('source_skill_id',sa.String(36),sa.ForeignKey('skills.id'),nullable=False),
        sa.Column('target_skill_id',sa.String(36),sa.ForeignKey('skills.id'),nullable=False),
        sa.Column('relation_type',sa.String(24),nullable=False),
        sa.Column('source_reference',sa.String(500),nullable=False),
        sa.Column('justification',sa.Text(),nullable=False),
        sa.Column('country_code',sa.String(2),nullable=False),
        sa.Column('reviewed_by',sa.String(36),sa.ForeignKey('users.id'),nullable=False),
        sa.Column('version',sa.Integer(),nullable=False),
        sa.Column('verified_at',sa.DateTime(),nullable=False),
        sa.UniqueConstraint('organization_id','source_skill_id','target_skill_id','relation_type',name='uq_africa_relation'))
    op.create_index('ix_africa_relation_org_source','africa_skill_relations',['organization_id','source_skill_id'])
    op.create_index('ix_africa_relation_org_target','africa_skill_relations',['organization_id','target_skill_id'])
    op.create_table('opportunity_preferences',
        sa.Column('id',sa.String(36),primary_key=True),
        sa.Column('organization_id',sa.String(36),sa.ForeignKey('organizations.id',ondelete='CASCADE'),nullable=False),
        sa.Column('candidate_id',sa.String(36),sa.ForeignKey('candidates.id',ondelete='CASCADE'),nullable=False),
        sa.Column('consent_state',sa.String(25),nullable=False),
        sa.Column('evidence_reference',sa.String(250)),
        sa.Column('updated_by',sa.String(36),sa.ForeignKey('users.id'),nullable=False),
        sa.Column('updated_at',sa.DateTime(),nullable=False),
        sa.UniqueConstraint('organization_id','candidate_id',name='uq_opportunity_preference_org_candidate'))
    op.create_index('ix_opportunity_preferences_organization_id','opportunity_preferences',['organization_id'])
    op.create_index('ix_opportunity_preferences_candidate_id','opportunity_preferences',['candidate_id'])

def downgrade():
    op.drop_index('ix_opportunity_preferences_candidate_id',table_name='opportunity_preferences')
    op.drop_index('ix_opportunity_preferences_organization_id',table_name='opportunity_preferences')
    op.drop_table('opportunity_preferences')
    op.drop_index('ix_africa_relation_org_target',table_name='africa_skill_relations')
    op.drop_index('ix_africa_relation_org_source',table_name='africa_skill_relations')
    op.drop_table('africa_skill_relations')

"""Report export metadata, without persisting raw candidate report copies.

Revision ID: 0006_reports
Revises: 0005_matching
"""
from alembic import op
import sqlalchemy as sa

revision = '0006_reports'
down_revision = '0005_matching'
branch_labels = None
depends_on = None

def upgrade():
    op.create_table('report_exports',
        sa.Column('id',sa.String(36),primary_key=True),
        sa.Column('organization_id',sa.String(36),sa.ForeignKey('organizations.id',ondelete='CASCADE'),nullable=False),
        sa.Column('campaign_id',sa.String(36),sa.ForeignKey('recruitment_campaigns.id'),nullable=False),
        sa.Column('run_id',sa.String(36),sa.ForeignKey('matching_runs.id'),nullable=False),
        sa.Column('format',sa.String(8),nullable=False),
        sa.Column('row_count',sa.Integer(),nullable=False),
        sa.Column('sha256',sa.String(64),nullable=False),
        sa.Column('created_by',sa.String(36),sa.ForeignKey('users.id'),nullable=False),
        sa.Column('created_at',sa.DateTime(),nullable=False),
    )
    op.create_index('ix_report_export_org_created','report_exports',['organization_id','created_at'])

def downgrade():
    op.drop_index('ix_report_export_org_created',table_name='report_exports')
    op.drop_table('report_exports')

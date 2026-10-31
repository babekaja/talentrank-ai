"""ORM mappings for the schema defined by the versioned Alembic migrations.

The source archive omitted its models package. Reflecting the migrated schema
keeps these mappings aligned with the actual database without duplicating DDL.
"""

from sqlalchemy import ColumnDefault
from sqlalchemy.orm import relationship

from app.core.database import Base, engine
from app.models.auth import uid, utcnow


TABLE_CLASSES = {
    'organizations': 'Organization',
    'users': 'User',
    'organization_members': 'OrganizationMember',
    'user_sessions': 'UserSession',
    'audit_logs': 'AuditLog',
    'invitations': 'Invitation',
    'jobs': 'Job',
    'job_requirements': 'JobRequirement',
    'recruitment_campaigns': 'RecruitmentCampaign',
    'candidates': 'Candidate',
    'candidate_contacts': 'CandidateContact',
    'applications': 'Application',
    'application_reviews': 'ApplicationReview',
    'upload_batches': 'UploadBatch',
    'cv_documents': 'CVDocument',
    'document_pages': 'DocumentPage',
    'extraction_warnings': 'ExtractionWarning',
    'processing_tasks': 'ProcessingTask',
    'skills': 'Skill',
    'skill_aliases': 'SkillAlias',
    'organization_skill_aliases': 'OrganizationSkillAlias',
    'document_nlp_runs': 'DocumentNlpRun',
    'skill_evidence': 'SkillEvidence',
    'matching_configurations': 'MatchingConfiguration',
    'matching_runs': 'MatchingRun',
    'matching_results': 'MatchingResult',
    'matching_criteria_results': 'MatchingCriterionResult',
    'matching_evidence': 'MatchingEvidence',
    'report_exports': 'ReportExport',
    'retention_policies': 'RetentionPolicy',
    'candidate_legal_holds': 'CandidateLegalHold',
    'document_facts': 'DocumentFact',
    'application_assignments': 'ApplicationAssignment',
    'training_courses': 'TrainingCourse',
    'africa_skill_relations': 'SkillRelation',
    'opportunity_preferences': 'OpportunityPreference',
    'candidate_portal_tokens': 'CandidatePortalToken',
    'candidate_portal_sessions': 'CandidatePortalSession',
    'candidate_consent_events': 'CandidateConsentEvent',
}

Base.metadata.reflect(bind=engine)
missing = set(TABLE_CLASSES) - set(Base.metadata.tables)
if missing:
    raise RuntimeError(f'Database migrations are missing tables: {sorted(missing)}')

for table_name, class_name in TABLE_CLASSES.items():
    table = Base.metadata.tables[table_name]
    if 'id' in table.c and table.c.id.primary_key:
        table.c.id.default = ColumnDefault(uid)
    for name in ('created_at', 'updated_at', 'verified_at'):
        if name in table.c:
            table.c[name].default = ColumnDefault(utcnow)
    if 'is_active' in table.c:
        table.c.is_active.default = ColumnDefault(True)
    if 'active' in table.c:
        table.c.active.default = ColumnDefault(True)
    if table_name == 'skill_aliases':
        table.c.language.default = ColumnDefault('und')
    if table_name == 'jobs':
        table.c.status.default = ColumnDefault('draft')
        table.c.criteria_version.default = ColumnDefault(0)
    if table_name == 'recruitment_campaigns':
        table.c.status.default = ColumnDefault('planned')
    if table_name == 'applications':
        table.c.review_status.default = ColumnDefault('to_review')
    if table_name == 'cv_documents':
        table.c.attempt_count.default = ColumnDefault(0)
        table.c.page_count.default = ColumnDefault(0)
    if table_name == 'processing_tasks':
        table.c.attempts.default = ColumnDefault(0)
    if table_name == 'document_pages':
        table.c.verification_status.default = ColumnDefault('unverified')
    if table_name == 'matching_runs':
        table.c.status.default = ColumnDefault('queued')
        table.c.processed.default = ColumnDefault(0)
    globals()[class_name] = type(class_name, (Base,), {'__table__': table})

Candidate.contacts = relationship(
    CandidateContact, uselist=False, back_populates='candidate',
    cascade='all, delete-orphan', single_parent=True,
)
CandidateContact.candidate = relationship(Candidate, back_populates='contacts')
Job.requirements = relationship(
    JobRequirement, back_populates='job', cascade='all, delete-orphan',
)
JobRequirement.job = relationship(Job, back_populates='requirements')

__all__ = list(TABLE_CLASSES.values())

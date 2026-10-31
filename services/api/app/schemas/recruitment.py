from datetime import date, datetime
from typing import Literal
from pydantic import BaseModel, ConfigDict, EmailStr, Field, model_validator

Role = Literal['org_admin', 'recruiter', 'evaluator']
Category = Literal['skill', 'experience', 'qualification', 'certification', 'language', 'other']


class ORMOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)


class InviteIn(BaseModel):
    email: EmailStr
    role: Role


class InvitationOut(ORMOut):
    id: str
    email: EmailStr
    role: Role
    expires_at: datetime
    accepted_at: datetime | None
    revoked_at: datetime | None


class InvitationCreated(InvitationOut):
    token: str


class AcceptInvitationIn(BaseModel):
    token: str = Field(min_length=32, max_length=256)
    full_name: str = Field(min_length=2, max_length=180)
    password: str = Field(min_length=12, max_length=256)


class MemberOut(ORMOut):
    id: str
    user_id: str
    full_name: str
    email: EmailStr
    role: Role
    is_active: bool


class MemberPatch(BaseModel):
    role: Role | None = None
    is_active: bool | None = None


class RequirementIn(BaseModel):
    code: str = Field(min_length=2, max_length=50, pattern=r'^[a-zA-Z0-9_-]+$')
    label: str = Field(min_length=2, max_length=160)
    category: Category
    required: bool
    weight: int = Field(default=1, ge=1, le=100)
    justification: str = Field(min_length=5, max_length=2000)
    skill_ref: str | None = Field(default=None, max_length=120)


class RequirementOut(ORMOut):
    id: str
    code: str
    label: str
    category: Category
    required: bool
    weight: int
    justification: str
    skill_ref: str | None
    resolved_skill_id: str | None = None


class RequirementsReplace(BaseModel):
    items: list[RequirementIn] = Field(min_length=1, max_length=100)
    @model_validator(mode='after')
    def unique_codes(self):
        codes = [item.code.lower() for item in self.items]
        if len(codes) != len(set(codes)):
            raise ValueError('Les codes de critères doivent être uniques')
        return self


class JobIn(BaseModel):
    title: str = Field(min_length=3, max_length=180)
    department: str | None = Field(default=None, max_length=120)
    location: str | None = Field(default=None, max_length=180)
    contract_type: str | None = Field(default=None, max_length=60)
    work_mode: Literal['onsite', 'remote', 'hybrid'] | None = None
    description: str = Field(min_length=10, max_length=20000)
    opens_on: date | None = None
    closes_on: date | None = None

    @model_validator(mode='after')
    def dates_valid(self):
        if self.opens_on and self.closes_on and self.closes_on < self.opens_on:
            raise ValueError('La date de clôture doit suivre la date d’ouverture')
        return self


class JobPatch(JobIn):
    pass


class JobOut(ORMOut):
    id: str
    title: str
    department: str | None
    location: str | None
    contract_type: str | None
    work_mode: str | None
    description: str
    status: str
    opens_on: date | None
    closes_on: date | None
    criteria_version: int
    criteria_confirmed_at: datetime | None
    created_at: datetime
    requirements: list[RequirementOut]


class CampaignIn(BaseModel):
    job_id: str
    name: str = Field(min_length=3, max_length=180)


class CampaignStatusIn(BaseModel):
    status: Literal['planned', 'active', 'closed']


class CampaignOut(ORMOut):
    id: str
    job_id: str
    name: str
    status: str
    created_at: datetime


class CandidateIn(BaseModel):
    full_name: str = Field(min_length=2, max_length=180)
    email: EmailStr | None = None
    phone: str | None = Field(default=None, max_length=50)


class CandidateOut(BaseModel):
    id: str
    reference: str
    full_name: str
    email: EmailStr | None = None
    phone: str | None = None
    created_at: datetime


class ApplicationIn(BaseModel):
    campaign_id: str
    candidate_id: str


class ApplicationOut(ORMOut):
    id: str
    campaign_id: str
    candidate_id: str
    review_status: str
    created_at: datetime


class ReviewIn(BaseModel):
    finding: Literal['reviewed', 'needs_clarification', 'shortlisted']
    note: str = Field(min_length=3, max_length=4000)


class ReviewOut(ORMOut):
    id: str
    application_id: str
    author_id: str
    finding: str
    note: str
    created_at: datetime


class Page(BaseModel):
    items: list
    total: int
    limit: int
    offset: int

class JobUpdate(BaseModel):
    title: str | None = Field(default=None, min_length=3, max_length=180)
    department: str | None = Field(default=None, max_length=120)
    location: str | None = Field(default=None, max_length=180)
    contract_type: str | None = Field(default=None, max_length=60)
    work_mode: Literal['onsite', 'remote', 'hybrid'] | None = None
    description: str | None = Field(default=None, min_length=10, max_length=20000)
    opens_on: date | None = None
    closes_on: date | None = None


class ConfirmRequirementsIn(BaseModel):
    expected_version: int = Field(ge=1)

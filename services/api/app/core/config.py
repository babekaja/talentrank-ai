from functools import lru_cache
from typing import Literal

from pydantic import Field, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file='.env', extra='ignore')

    environment: Literal['development', 'test', 'production'] = 'development'
    database_url: str = 'sqlite:///./talentrank-dev.sqlite3'
    jwt_secret: str = Field(min_length=32)
    jwt_issuer: str = 'talentrank-ai'
    jwt_audience: str = 'talentrank-web'
    cors_origins: str = 'http://localhost:4200,http://localhost:8080'
    refresh_cookie_secure: bool = False
    demo_enabled: bool = False
    demo_user_email: str = 'demo@babetech.example.org'
    demo_organization_slug: str = 'babetech'
    demo_allow_writes: bool = False
    redis_url: str = 'redis://redis:6379/0'
    s3_endpoint: str = 'minio:9000'
    s3_access_key: str = 'talentrank'
    s3_secret_key: str = 'CHANGE_ME_OBJECT_STORAGE_SECRET'
    s3_bucket: str = 'cv-private'
    s3_secure: bool = False
    max_cv_bytes: int = Field(default=60_000_000, ge=1024, le=100_000_000)
    max_zip_bytes: int = Field(default=100_000_000, ge=1024, le=2_000_000_000)
    max_batch_documents: int = Field(default=3000, ge=1, le=10000)
    malware_scan_enabled: bool = False
    clamav_host: str = 'clamav'
    clamav_port: int = 3310
    # Optional semantic model service is local only, disabled in standard installation.
    semantic_enabled: bool = False
    embedding_model: str = 'sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2'
    ml_service_url: str = 'http://ml-service:8090'
    ml_service_token: str = 'CHANGE_ME_ML_INTERNAL_TOKEN'
    qdrant_url: str = 'http://qdrant:6333'
    candidate_portal_enabled: bool = False
    candidate_portal_smtp_host: str = ''
    candidate_portal_smtp_port: int = Field(default=587, ge=1, le=65535)
    candidate_portal_smtp_user: str = ''
    candidate_portal_smtp_password: str = ''
    candidate_portal_from_email: str = ''
    candidate_portal_base_url: str = 'http://localhost:8080'
    ocr_languages: str = 'fra+eng'
    max_pdf_pages: int = Field(default=40, ge=1, le=200)
    max_docx_paragraphs: int = Field(default=10000, ge=10)


    @property
    def origins(self) -> list[str]:
        return [x.strip() for x in self.cors_origins.split(',') if x.strip()]

    @model_validator(mode='after')
    def protect_production(self):
        if self.environment == 'production' and (
            not self.refresh_cookie_secure
            or not self.origins
            or any(not origin.startswith('https://') or '*' in origin for origin in self.origins)
            or not self.database_url.startswith('mysql+pymysql://')
            or self.jwt_secret.startswith(('CHANGE_', 'REPLACE_'))
            or self.s3_secret_key.startswith('CHANGE_')
            or not self.malware_scan_enabled
            or (self.semantic_enabled and self.ml_service_token.startswith('CHANGE_'))
            or (self.candidate_portal_enabled and (not self.candidate_portal_smtp_host
                or not self.candidate_portal_from_email
                or not self.candidate_portal_base_url.startswith('https://')))
        ):
            raise ValueError('La production exige MySQL, CORS HTTPS, secrets et antivirus actif')
        return self


@lru_cache
def get_settings() -> Settings:
    return Settings()

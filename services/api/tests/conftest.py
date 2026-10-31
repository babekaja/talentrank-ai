import atexit
import os
import tempfile
from pathlib import Path

os.environ['ENVIRONMENT'] = 'test'
os.environ['JWT_SECRET'] = 'testing-only-super-long-secret-change-in-real-use-0123456789'

# The ORM reflects the versioned schema at import time. Give it a disposable,
# migrated SQLite database instead of an empty in-memory connection. Individual
# fixtures still use isolated in-memory databases created from that metadata.
_schema_file = tempfile.NamedTemporaryFile(prefix='talentrank-test-schema-', suffix='.sqlite3', delete=False)
_schema_file.close()
os.environ['DATABASE_URL'] = f'sqlite:///{_schema_file.name}'
_api_root = Path(__file__).resolve().parents[1]
from alembic import command
from alembic.config import Config
_alembic = Config(str(_api_root / 'alembic.ini'))
_alembic.set_main_option('script_location', str(_api_root / 'alembic'))
command.upgrade(_alembic, 'head')
atexit.register(lambda: Path(_schema_file.name).unlink(missing_ok=True))

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.core.database import Base, get_db
from app.core.security import hash_password
from app.main import app
from app.models import Organization, OrganizationMember, User


@pytest.fixture
def client_and_orgs():
    engine = create_engine('sqlite://', connect_args={'check_same_thread': False}, poolclass=StaticPool)
    Base.metadata.create_all(engine)
    factory = sessionmaker(bind=engine, expire_on_commit=False)
    with factory.begin() as session:
        first = Organization(name='Organisation Alpha', slug='alpha')
        second = Organization(name='Organisation Beta', slug='beta')
        user = User(email='admin@alpha.example.org', full_name='Alex Alpha',
                    password_hash=hash_password('a-good-password-123'))
        session.add_all([first, second, user])
        session.flush()
        membership = OrganizationMember(user_id=user.id, organization_id=first.id, role='org_admin')
        session.add(membership)
        ids = {'alpha': first.id, 'beta': second.id}

    def db_override():
        with factory() as session:
            yield session

    app.dependency_overrides[get_db] = db_override
    try:
        with TestClient(app) as client:
            yield client, ids
    finally:
        app.dependency_overrides.clear()
        Base.metadata.drop_all(engine)
        engine.dispose()

import asyncio
import logging
from typing import AsyncGenerator

import pytest
import pytest_asyncio
from httpx import ASGITransport, AsyncClient
from sqlalchemy.ext.asyncio import (
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)

from app.core.database import Base, get_db
from app.core.security import hash_password
from app.main import app
from app.models.user import User
from app.models.department import Department
from app.models.skill import Skill
from app.models.job_posting import JobPosting
from app.models.candidate import Candidate
from app.models.application import Application
from app.models.interview import Interview
from app.models.audit_log import ActivityLog

logger = logging.getLogger(__name__)

TEST_DATABASE_URL = "sqlite+aiosqlite:///:memory:"

test_engine = create_async_engine(
    TEST_DATABASE_URL,
    echo=False,
    pool_pre_ping=True,
)

test_async_session_factory = async_sessionmaker(
    test_engine,
    class_=AsyncSession,
    expire_on_commit=False,
)


@pytest.fixture(scope="session")
def event_loop():
    """Create a single event loop for the entire test session."""
    policy = asyncio.get_event_loop_policy()
    loop = policy.new_event_loop()
    yield loop
    loop.close()


@pytest_asyncio.fixture(autouse=True)
async def setup_database():
    """Create all tables before each test and drop them after."""
    async with test_engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    yield
    async with test_engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)
    await test_engine.dispose()


@pytest_asyncio.fixture
async def db_session() -> AsyncGenerator[AsyncSession, None]:
    """Provide a test database session."""
    async with test_async_session_factory() as session:
        try:
            yield session
            await session.commit()
        except Exception:
            await session.rollback()
            raise
        finally:
            await session.close()


@pytest_asyncio.fixture
async def client(db_session: AsyncSession) -> AsyncGenerator[AsyncClient, None]:
    """Provide an async HTTP test client with the test database session injected."""

    async def _override_get_db() -> AsyncGenerator[AsyncSession, None]:
        try:
            yield db_session
            await db_session.commit()
        except Exception:
            await db_session.rollback()
            raise

    app.dependency_overrides[get_db] = _override_get_db

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://testserver") as ac:
        yield ac

    app.dependency_overrides.clear()


@pytest_asyncio.fixture
async def admin_user(db_session: AsyncSession) -> User:
    """Create and return an admin user for testing."""
    user = User(
        username="testadmin",
        email="testadmin@talentflow.local",
        hashed_password=hash_password("adminpass123"),
        full_name="Test Administrator",
        role="admin",
        is_active=1,
    )
    db_session.add(user)
    await db_session.flush()
    await db_session.refresh(user)
    return user


@pytest_asyncio.fixture
async def recruiter_user(db_session: AsyncSession) -> User:
    """Create and return a recruiter user for testing."""
    user = User(
        username="testrecruiter",
        email="testrecruiter@talentflow.local",
        hashed_password=hash_password("recruiterpass123"),
        full_name="Test Recruiter",
        role="recruiter",
        is_active=1,
    )
    db_session.add(user)
    await db_session.flush()
    await db_session.refresh(user)
    return user


@pytest_asyncio.fixture
async def hiring_manager_user(db_session: AsyncSession) -> User:
    """Create and return a hiring manager user for testing."""
    user = User(
        username="testhiringmgr",
        email="testhiringmgr@talentflow.local",
        hashed_password=hash_password("managerpass123"),
        full_name="Test Hiring Manager",
        role="hiring_manager",
        is_active=1,
    )
    db_session.add(user)
    await db_session.flush()
    await db_session.refresh(user)
    return user


@pytest_asyncio.fixture
async def interviewer_user(db_session: AsyncSession) -> User:
    """Create and return an interviewer user for testing."""
    user = User(
        username="testinterviewer",
        email="testinterviewer@talentflow.local",
        hashed_password=hash_password("interviewerpass123"),
        full_name="Test Interviewer",
        role="interviewer",
        is_active=1,
    )
    db_session.add(user)
    await db_session.flush()
    await db_session.refresh(user)
    return user


@pytest_asyncio.fixture
async def viewer_user(db_session: AsyncSession) -> User:
    """Create and return a viewer (read-only) user for testing."""
    user = User(
        username="testviewer",
        email="testviewer@talentflow.local",
        hashed_password=hash_password("viewerpass123"),
        full_name="Test Viewer",
        role="viewer",
        is_active=1,
    )
    db_session.add(user)
    await db_session.flush()
    await db_session.refresh(user)
    return user


@pytest_asyncio.fixture
async def test_department(db_session: AsyncSession) -> Department:
    """Create and return a test department."""
    department = Department(name="Test Engineering")
    db_session.add(department)
    await db_session.flush()
    await db_session.refresh(department)
    return department


@pytest_asyncio.fixture
async def test_departments(db_session: AsyncSession) -> list[Department]:
    """Create and return multiple test departments."""
    names = ["Engineering", "Marketing", "Sales", "HR"]
    departments = []
    for name in names:
        dept = Department(name=name)
        db_session.add(dept)
        departments.append(dept)
    await db_session.flush()
    for dept in departments:
        await db_session.refresh(dept)
    return departments


@pytest_asyncio.fixture
async def test_skills(db_session: AsyncSession) -> list[Skill]:
    """Create and return multiple test skills."""
    skill_names = ["Python", "FastAPI", "SQL", "Docker", "React"]
    skills = []
    for name in skill_names:
        skill = Skill(name=name)
        db_session.add(skill)
        skills.append(skill)
    await db_session.flush()
    for skill in skills:
        await db_session.refresh(skill)
    return skills


@pytest_asyncio.fixture
async def test_job(
    db_session: AsyncSession,
    test_department: Department,
    admin_user: User,
) -> JobPosting:
    """Create and return a published test job posting."""
    job = JobPosting(
        title="Senior Python Developer",
        description="We are looking for an experienced Python developer.",
        status="Published",
        department_id=test_department.id,
        hiring_manager_id=admin_user.id,
        location="Remote",
        type="Full-Time",
        salary_min=100000,
        salary_max=150000,
    )
    db_session.add(job)
    await db_session.flush()
    await db_session.refresh(job)
    return job


@pytest_asyncio.fixture
async def test_draft_job(
    db_session: AsyncSession,
    test_department: Department,
    admin_user: User,
) -> JobPosting:
    """Create and return a draft test job posting."""
    job = JobPosting(
        title="Junior Frontend Developer",
        description="Entry-level frontend position.",
        status="Draft",
        department_id=test_department.id,
        hiring_manager_id=admin_user.id,
        location="New York, NY",
        type="Full-Time",
        salary_min=60000,
        salary_max=80000,
    )
    db_session.add(job)
    await db_session.flush()
    await db_session.refresh(job)
    return job


@pytest_asyncio.fixture
async def test_candidate(db_session: AsyncSession) -> Candidate:
    """Create and return a test candidate."""
    candidate = Candidate(
        first_name="Jane",
        last_name="Doe",
        email="jane.doe@example.com",
        phone="+1-555-123-4567",
        linkedin_url="https://linkedin.com/in/janedoe",
        resume_text="Experienced software engineer with 5 years of Python development.",
    )
    db_session.add(candidate)
    await db_session.flush()
    await db_session.refresh(candidate)
    return candidate


@pytest_asyncio.fixture
async def test_candidate_with_skills(
    db_session: AsyncSession,
    test_skills: list[Skill],
) -> Candidate:
    """Create and return a test candidate with skills attached."""
    candidate = Candidate(
        first_name="John",
        last_name="Smith",
        email="john.smith@example.com",
        phone="+1-555-987-6543",
        resume_text="Full-stack developer proficient in Python and React.",
    )
    candidate.skills = test_skills[:3]
    db_session.add(candidate)
    await db_session.flush()
    await db_session.refresh(candidate)
    return candidate


@pytest_asyncio.fixture
async def test_application(
    db_session: AsyncSession,
    test_candidate: Candidate,
    test_job: JobPosting,
) -> Application:
    """Create and return a test application."""
    application = Application(
        candidate_id=test_candidate.id,
        job_id=test_job.id,
        stage="Applied",
    )
    db_session.add(application)
    await db_session.flush()
    await db_session.refresh(application)
    return application


@pytest_asyncio.fixture
async def test_interview(
    db_session: AsyncSession,
    test_application: Application,
    interviewer_user: User,
) -> Interview:
    """Create and return a test interview."""
    from datetime import datetime, timedelta

    interview = Interview(
        application_id=test_application.id,
        interviewer_id=interviewer_user.id,
        scheduled_at=datetime.utcnow() + timedelta(days=3),
    )
    db_session.add(interview)
    await db_session.flush()
    await db_session.refresh(interview)
    return interview


def get_auth_cookie(user: User) -> dict[str, str]:
    """Generate a session cookie dict for the given user.

    Use this to authenticate requests in tests:
        client.cookies.update(get_auth_cookie(user))
    """
    from app.core.security import create_session_token

    token = create_session_token(
        {
            "user_id": user.id,
            "username": user.username,
            "role": user.role,
        }
    )
    return {"session": token}


@pytest_asyncio.fixture
async def authenticated_admin_client(
    client: AsyncClient,
    admin_user: User,
) -> AsyncClient:
    """Provide an async HTTP test client authenticated as admin."""
    client.cookies.update(get_auth_cookie(admin_user))
    return client


@pytest_asyncio.fixture
async def authenticated_recruiter_client(
    client: AsyncClient,
    recruiter_user: User,
) -> AsyncClient:
    """Provide an async HTTP test client authenticated as recruiter."""
    client.cookies.update(get_auth_cookie(recruiter_user))
    return client


@pytest_asyncio.fixture
async def authenticated_interviewer_client(
    client: AsyncClient,
    interviewer_user: User,
) -> AsyncClient:
    """Provide an async HTTP test client authenticated as interviewer."""
    client.cookies.update(get_auth_cookie(interviewer_user))
    return client
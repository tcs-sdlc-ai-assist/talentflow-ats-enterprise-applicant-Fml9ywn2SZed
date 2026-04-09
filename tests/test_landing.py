import logging
from typing import AsyncGenerator

import pytest
import pytest_asyncio
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.department import Department
from app.models.job_posting import JobPosting
from app.models.user import User
from tests.conftest import get_auth_cookie

logger = logging.getLogger(__name__)


@pytest.mark.asyncio
async def test_landing_page_returns_200(client: AsyncClient):
    """GET / returns 200 OK without authentication."""
    response = await client.get("/")
    assert response.status_code == 200


@pytest.mark.asyncio
async def test_landing_page_contains_html(client: AsyncClient):
    """GET / returns valid HTML content."""
    response = await client.get("/")
    assert response.status_code == 200
    assert "text/html" in response.headers.get("content-type", "")
    assert "TalentFlow" in response.text


@pytest.mark.asyncio
async def test_landing_page_no_auth_required(client: AsyncClient):
    """GET / does not require authentication — no session cookie needed."""
    response = await client.get("/", follow_redirects=False)
    assert response.status_code == 200


@pytest.mark.asyncio
async def test_landing_page_shows_login_cta(client: AsyncClient):
    """GET / contains a login CTA link pointing to /auth/login."""
    response = await client.get("/")
    assert response.status_code == 200
    assert "/auth/login" in response.text


@pytest.mark.asyncio
async def test_landing_page_shows_published_jobs(
    client: AsyncClient,
    test_job: JobPosting,
):
    """GET / displays published job postings."""
    response = await client.get("/")
    assert response.status_code == 200
    assert test_job.title in response.text


@pytest.mark.asyncio
async def test_landing_page_hides_draft_jobs(
    client: AsyncClient,
    test_draft_job: JobPosting,
):
    """GET / does not display draft job postings."""
    response = await client.get("/")
    assert response.status_code == 200
    assert test_draft_job.title not in response.text


@pytest.mark.asyncio
async def test_landing_page_hides_closed_jobs(
    client: AsyncClient,
    db_session: AsyncSession,
    test_department: Department,
    admin_user: User,
):
    """GET / does not display closed job postings."""
    closed_job = JobPosting(
        title="Closed Position XYZ",
        description="This position has been filled.",
        status="Closed",
        department_id=test_department.id,
        hiring_manager_id=admin_user.id,
        location="Boston, MA",
        type="Full-Time",
    )
    db_session.add(closed_job)
    await db_session.flush()
    await db_session.refresh(closed_job)

    response = await client.get("/")
    assert response.status_code == 200
    assert "Closed Position XYZ" not in response.text


@pytest.mark.asyncio
async def test_landing_page_shows_multiple_published_jobs(
    client: AsyncClient,
    db_session: AsyncSession,
    test_department: Department,
    admin_user: User,
):
    """GET / displays all published job postings."""
    job1 = JobPosting(
        title="Backend Engineer Alpha",
        description="Backend role.",
        status="Published",
        department_id=test_department.id,
        hiring_manager_id=admin_user.id,
        location="Remote",
        type="Full-Time",
    )
    job2 = JobPosting(
        title="Frontend Engineer Beta",
        description="Frontend role.",
        status="Published",
        department_id=test_department.id,
        hiring_manager_id=admin_user.id,
        location="San Francisco, CA",
        type="Full-Time",
    )
    db_session.add(job1)
    db_session.add(job2)
    await db_session.flush()

    response = await client.get("/")
    assert response.status_code == 200
    assert "Backend Engineer Alpha" in response.text
    assert "Frontend Engineer Beta" in response.text


@pytest.mark.asyncio
async def test_landing_page_shows_only_published_not_draft_or_closed(
    client: AsyncClient,
    db_session: AsyncSession,
    test_department: Department,
    admin_user: User,
):
    """GET / shows published jobs but not draft or closed ones."""
    published_job = JobPosting(
        title="Published Role Gamma",
        description="Active published role.",
        status="Published",
        department_id=test_department.id,
        hiring_manager_id=admin_user.id,
        location="Remote",
        type="Full-Time",
    )
    draft_job = JobPosting(
        title="Draft Role Delta",
        description="Not yet published.",
        status="Draft",
        department_id=test_department.id,
        hiring_manager_id=admin_user.id,
        location="Remote",
        type="Full-Time",
    )
    closed_job = JobPosting(
        title="Closed Role Epsilon",
        description="No longer open.",
        status="Closed",
        department_id=test_department.id,
        hiring_manager_id=admin_user.id,
        location="Remote",
        type="Full-Time",
    )
    db_session.add_all([published_job, draft_job, closed_job])
    await db_session.flush()

    response = await client.get("/")
    assert response.status_code == 200
    assert "Published Role Gamma" in response.text
    assert "Draft Role Delta" not in response.text
    assert "Closed Role Epsilon" not in response.text


@pytest.mark.asyncio
async def test_landing_page_empty_state_no_jobs(client: AsyncClient):
    """GET / renders correctly when there are no published jobs."""
    response = await client.get("/")
    assert response.status_code == 200
    # The template shows an empty state message when no jobs exist
    assert "No open positions" in response.text or "Open Positions" in response.text


@pytest.mark.asyncio
async def test_landing_page_shows_department_name(
    client: AsyncClient,
    test_job: JobPosting,
    test_department: Department,
):
    """GET / displays the department name for published jobs."""
    response = await client.get("/")
    assert response.status_code == 200
    assert test_department.name in response.text


@pytest.mark.asyncio
async def test_landing_page_shows_job_location(
    client: AsyncClient,
    test_job: JobPosting,
):
    """GET / displays the location for published jobs."""
    response = await client.get("/")
    assert response.status_code == 200
    assert test_job.location in response.text


@pytest.mark.asyncio
async def test_landing_page_shows_salary_range(
    client: AsyncClient,
    test_job: JobPosting,
):
    """GET / displays salary range for published jobs that have salary info."""
    response = await client.get("/")
    assert response.status_code == 200
    # test_job has salary_min=100000 and salary_max=150000
    assert "100,000" in response.text
    assert "150,000" in response.text


@pytest.mark.asyncio
async def test_landing_page_accessible_when_authenticated(
    client: AsyncClient,
    admin_user: User,
    test_job: JobPosting,
):
    """GET / works for authenticated users and still shows published jobs."""
    client.cookies.update(get_auth_cookie(admin_user))
    response = await client.get("/")
    assert response.status_code == 200
    assert test_job.title in response.text


@pytest.mark.asyncio
async def test_landing_page_shows_register_link(client: AsyncClient):
    """GET / contains a link to the registration page."""
    response = await client.get("/")
    assert response.status_code == 200
    assert "/auth/register" in response.text


@pytest.mark.asyncio
async def test_landing_page_hero_section(client: AsyncClient):
    """GET / contains the hero section with welcome text."""
    response = await client.get("/")
    assert response.status_code == 200
    assert "Welcome to TalentFlow" in response.text


@pytest.mark.asyncio
async def test_landing_page_stats_section(
    client: AsyncClient,
    test_job: JobPosting,
):
    """GET / contains the stats section showing open positions count."""
    response = await client.get("/")
    assert response.status_code == 200
    assert "Open Positions" in response.text
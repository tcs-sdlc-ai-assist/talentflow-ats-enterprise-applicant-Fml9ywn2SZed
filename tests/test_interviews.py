import logging
from datetime import datetime, timedelta

import pytest
import pytest_asyncio
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.application import Application
from app.models.candidate import Candidate
from app.models.department import Department
from app.models.interview import Interview
from app.models.job_posting import JobPosting
from app.models.user import User
from app.core.security import hash_password
from tests.conftest import get_auth_cookie

logger = logging.getLogger(__name__)


# ── Fixtures ──────────────────────────────────────────────────────────────────


@pytest_asyncio.fixture
async def interview_department(db_session: AsyncSession) -> Department:
    dept = Department(name="Interview Test Dept")
    db_session.add(dept)
    await db_session.flush()
    await db_session.refresh(dept)
    return dept


@pytest_asyncio.fixture
async def interview_hiring_manager(db_session: AsyncSession) -> User:
    user = User(
        username="int_hm",
        email="int_hm@talentflow.local",
        hashed_password=hash_password("password123"),
        full_name="Interview Hiring Manager",
        role="hiring_manager",
        is_active=1,
    )
    db_session.add(user)
    await db_session.flush()
    await db_session.refresh(user)
    return user


@pytest_asyncio.fixture
async def interview_admin(db_session: AsyncSession) -> User:
    user = User(
        username="int_admin",
        email="int_admin@talentflow.local",
        hashed_password=hash_password("password123"),
        full_name="Interview Admin",
        role="admin",
        is_active=1,
    )
    db_session.add(user)
    await db_session.flush()
    await db_session.refresh(user)
    return user


@pytest_asyncio.fixture
async def interview_recruiter(db_session: AsyncSession) -> User:
    user = User(
        username="int_recruiter",
        email="int_recruiter@talentflow.local",
        hashed_password=hash_password("password123"),
        full_name="Interview Recruiter",
        role="recruiter",
        is_active=1,
    )
    db_session.add(user)
    await db_session.flush()
    await db_session.refresh(user)
    return user


@pytest_asyncio.fixture
async def interview_interviewer(db_session: AsyncSession) -> User:
    user = User(
        username="int_interviewer",
        email="int_interviewer@talentflow.local",
        hashed_password=hash_password("password123"),
        full_name="Interview Interviewer",
        role="interviewer",
        is_active=1,
    )
    db_session.add(user)
    await db_session.flush()
    await db_session.refresh(user)
    return user


@pytest_asyncio.fixture
async def interview_viewer(db_session: AsyncSession) -> User:
    user = User(
        username="int_viewer",
        email="int_viewer@talentflow.local",
        hashed_password=hash_password("password123"),
        full_name="Interview Viewer",
        role="viewer",
        is_active=1,
    )
    db_session.add(user)
    await db_session.flush()
    await db_session.refresh(user)
    return user


@pytest_asyncio.fixture
async def interview_job(
    db_session: AsyncSession,
    interview_department: Department,
    interview_admin: User,
) -> JobPosting:
    job = JobPosting(
        title="Interview Test Job",
        description="A job for interview testing.",
        status="Published",
        department_id=interview_department.id,
        hiring_manager_id=interview_admin.id,
        location="Remote",
        type="Full-Time",
        salary_min=80000,
        salary_max=120000,
    )
    db_session.add(job)
    await db_session.flush()
    await db_session.refresh(job)
    return job


@pytest_asyncio.fixture
async def interview_candidate(db_session: AsyncSession) -> Candidate:
    candidate = Candidate(
        first_name="Interview",
        last_name="Candidate",
        email="interview.candidate@example.com",
        phone="+1-555-000-1111",
    )
    db_session.add(candidate)
    await db_session.flush()
    await db_session.refresh(candidate)
    return candidate


@pytest_asyncio.fixture
async def interview_application(
    db_session: AsyncSession,
    interview_candidate: Candidate,
    interview_job: JobPosting,
) -> Application:
    application = Application(
        candidate_id=interview_candidate.id,
        job_id=interview_job.id,
        stage="Interviewing",
    )
    db_session.add(application)
    await db_session.flush()
    await db_session.refresh(application)
    return application


@pytest_asyncio.fixture
async def scheduled_interview(
    db_session: AsyncSession,
    interview_application: Application,
    interview_interviewer: User,
) -> Interview:
    interview = Interview(
        application_id=interview_application.id,
        interviewer_id=interview_interviewer.id,
        scheduled_at=datetime.utcnow() + timedelta(days=5),
    )
    db_session.add(interview)
    await db_session.flush()
    await db_session.refresh(interview)
    return interview


@pytest_asyncio.fixture
async def completed_interview(
    db_session: AsyncSession,
    interview_application: Application,
    interview_interviewer: User,
) -> Interview:
    interview = Interview(
        application_id=interview_application.id,
        interviewer_id=interview_interviewer.id,
        scheduled_at=datetime.utcnow() - timedelta(days=1),
        rating=4,
        feedback_notes="Strong candidate with good technical skills.",
    )
    db_session.add(interview)
    await db_session.flush()
    await db_session.refresh(interview)
    return interview


# ── Interview List Page Tests ─────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_interview_list_requires_login(client: AsyncClient):
    """Unauthenticated users should be rejected from the interview list."""
    response = await client.get("/interviews", follow_redirects=False)
    assert response.status_code == 401


@pytest.mark.asyncio
async def test_interview_list_accessible_by_admin(
    client: AsyncClient,
    interview_admin: User,
    scheduled_interview: Interview,
):
    """Admin users can access the interview list page."""
    client.cookies.update(get_auth_cookie(interview_admin))
    response = await client.get("/interviews", follow_redirects=False)
    assert response.status_code == 200
    assert b"Interviews" in response.content


@pytest.mark.asyncio
async def test_interview_list_accessible_by_interviewer(
    client: AsyncClient,
    interview_interviewer: User,
    scheduled_interview: Interview,
):
    """Interviewers can access the interview list page."""
    client.cookies.update(get_auth_cookie(interview_interviewer))
    response = await client.get("/interviews", follow_redirects=False)
    assert response.status_code == 200
    assert b"Interviews" in response.content


@pytest.mark.asyncio
async def test_interview_list_shows_scheduled_interviews(
    client: AsyncClient,
    interview_admin: User,
    scheduled_interview: Interview,
    interview_candidate: Candidate,
):
    """Interview list should display scheduled interviews with candidate info."""
    client.cookies.update(get_auth_cookie(interview_admin))
    response = await client.get("/interviews", follow_redirects=False)
    assert response.status_code == 200
    assert interview_candidate.first_name.encode() in response.content
    assert interview_candidate.last_name.encode() in response.content


@pytest.mark.asyncio
async def test_interview_list_filter_by_status_scheduled(
    client: AsyncClient,
    interview_admin: User,
    scheduled_interview: Interview,
):
    """Filtering by 'scheduled' status should return future interviews."""
    client.cookies.update(get_auth_cookie(interview_admin))
    response = await client.get(
        "/interviews?status_filter=scheduled", follow_redirects=False
    )
    assert response.status_code == 200


@pytest.mark.asyncio
async def test_interview_list_filter_by_status_pending_feedback(
    client: AsyncClient,
    interview_admin: User,
    scheduled_interview: Interview,
):
    """Filtering by 'pending_feedback' should return interviews without ratings."""
    client.cookies.update(get_auth_cookie(interview_admin))
    response = await client.get(
        "/interviews?status_filter=pending_feedback", follow_redirects=False
    )
    assert response.status_code == 200


@pytest.mark.asyncio
async def test_interview_list_search(
    client: AsyncClient,
    interview_admin: User,
    scheduled_interview: Interview,
    interview_candidate: Candidate,
):
    """Search should filter interviews by candidate name."""
    client.cookies.update(get_auth_cookie(interview_admin))
    response = await client.get(
        f"/interviews?search={interview_candidate.first_name}",
        follow_redirects=False,
    )
    assert response.status_code == 200
    assert interview_candidate.first_name.encode() in response.content


# ── My Interviews Page Tests ─────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_my_interviews_page(
    client: AsyncClient,
    interview_interviewer: User,
    scheduled_interview: Interview,
):
    """Interviewer can view their own interviews."""
    client.cookies.update(get_auth_cookie(interview_interviewer))
    response = await client.get("/interviews/my", follow_redirects=False)
    assert response.status_code == 200
    assert b"Interviews" in response.content


@pytest.mark.asyncio
async def test_my_interviews_requires_login(client: AsyncClient):
    """Unauthenticated users should be rejected from my interviews."""
    response = await client.get("/interviews/my", follow_redirects=False)
    assert response.status_code == 401


# ── Schedule Interview Page Tests ─────────────────────────────────────────────


@pytest.mark.asyncio
async def test_schedule_page_accessible_by_admin(
    client: AsyncClient,
    interview_admin: User,
    interview_application: Application,
):
    """Admin can access the schedule interview page."""
    client.cookies.update(get_auth_cookie(interview_admin))
    response = await client.get("/interviews/schedule", follow_redirects=False)
    assert response.status_code == 200
    assert b"Schedule Interview" in response.content


@pytest.mark.asyncio
async def test_schedule_page_accessible_by_recruiter(
    client: AsyncClient,
    interview_recruiter: User,
    interview_application: Application,
):
    """Recruiter can access the schedule interview page."""
    client.cookies.update(get_auth_cookie(interview_recruiter))
    response = await client.get("/interviews/schedule", follow_redirects=False)
    assert response.status_code == 200
    assert b"Schedule Interview" in response.content


@pytest.mark.asyncio
async def test_schedule_page_accessible_by_hiring_manager(
    client: AsyncClient,
    interview_hiring_manager: User,
    interview_application: Application,
):
    """Hiring manager can access the schedule interview page."""
    client.cookies.update(get_auth_cookie(interview_hiring_manager))
    response = await client.get("/interviews/schedule", follow_redirects=False)
    assert response.status_code == 200
    assert b"Schedule Interview" in response.content


@pytest.mark.asyncio
async def test_schedule_page_denied_for_interviewer(
    client: AsyncClient,
    interview_interviewer: User,
):
    """Interviewers should not be able to access the schedule page."""
    client.cookies.update(get_auth_cookie(interview_interviewer))
    response = await client.get("/interviews/schedule", follow_redirects=False)
    assert response.status_code == 403


@pytest.mark.asyncio
async def test_schedule_page_denied_for_viewer(
    client: AsyncClient,
    interview_viewer: User,
):
    """Viewers should not be able to access the schedule page."""
    client.cookies.update(get_auth_cookie(interview_viewer))
    response = await client.get("/interviews/schedule", follow_redirects=False)
    assert response.status_code == 403


@pytest.mark.asyncio
async def test_schedule_page_with_preselected_application(
    client: AsyncClient,
    interview_admin: User,
    interview_application: Application,
):
    """Schedule page should accept application_id query parameter."""
    client.cookies.update(get_auth_cookie(interview_admin))
    response = await client.get(
        f"/interviews/schedule?application_id={interview_application.id}",
        follow_redirects=False,
    )
    assert response.status_code == 200


# ── Schedule Interview Submit Tests ───────────────────────────────────────────


@pytest.mark.asyncio
async def test_schedule_interview_success(
    client: AsyncClient,
    interview_admin: User,
    interview_application: Application,
    interview_interviewer: User,
):
    """Admin can successfully schedule an interview."""
    client.cookies.update(get_auth_cookie(interview_admin))
    scheduled_time = (datetime.utcnow() + timedelta(days=7)).strftime(
        "%Y-%m-%dT%H:%M"
    )
    response = await client.post(
        "/interviews",
        data={
            "application_id": str(interview_application.id),
            "interviewer_id": str(interview_interviewer.id),
            "scheduled_at": scheduled_time,
        },
        follow_redirects=False,
    )
    assert response.status_code == 302
    assert "/interviews" in response.headers.get("location", "")


@pytest.mark.asyncio
async def test_schedule_interview_by_recruiter(
    client: AsyncClient,
    interview_recruiter: User,
    interview_application: Application,
    interview_interviewer: User,
):
    """Recruiter can successfully schedule an interview."""
    client.cookies.update(get_auth_cookie(interview_recruiter))
    scheduled_time = (datetime.utcnow() + timedelta(days=3)).strftime(
        "%Y-%m-%dT%H:%M"
    )
    response = await client.post(
        "/interviews",
        data={
            "application_id": str(interview_application.id),
            "interviewer_id": str(interview_interviewer.id),
            "scheduled_at": scheduled_time,
        },
        follow_redirects=False,
    )
    assert response.status_code == 302
    assert "/interviews" in response.headers.get("location", "")


@pytest.mark.asyncio
async def test_schedule_interview_denied_for_interviewer(
    client: AsyncClient,
    interview_interviewer: User,
    interview_application: Application,
):
    """Interviewers should not be able to schedule interviews."""
    client.cookies.update(get_auth_cookie(interview_interviewer))
    scheduled_time = (datetime.utcnow() + timedelta(days=3)).strftime(
        "%Y-%m-%dT%H:%M"
    )
    response = await client.post(
        "/interviews",
        data={
            "application_id": str(interview_application.id),
            "interviewer_id": str(interview_interviewer.id),
            "scheduled_at": scheduled_time,
        },
        follow_redirects=False,
    )
    assert response.status_code == 403


@pytest.mark.asyncio
async def test_schedule_interview_denied_for_viewer(
    client: AsyncClient,
    interview_viewer: User,
    interview_application: Application,
    interview_interviewer: User,
):
    """Viewers should not be able to schedule interviews."""
    client.cookies.update(get_auth_cookie(interview_viewer))
    scheduled_time = (datetime.utcnow() + timedelta(days=3)).strftime(
        "%Y-%m-%dT%H:%M"
    )
    response = await client.post(
        "/interviews",
        data={
            "application_id": str(interview_application.id),
            "interviewer_id": str(interview_interviewer.id),
            "scheduled_at": scheduled_time,
        },
        follow_redirects=False,
    )
    assert response.status_code == 403


@pytest.mark.asyncio
async def test_schedule_interview_invalid_application_id(
    client: AsyncClient,
    interview_admin: User,
    interview_interviewer: User,
):
    """Scheduling with an invalid application ID should return 400."""
    client.cookies.update(get_auth_cookie(interview_admin))
    scheduled_time = (datetime.utcnow() + timedelta(days=3)).strftime(
        "%Y-%m-%dT%H:%M"
    )
    response = await client.post(
        "/interviews",
        data={
            "application_id": "not-a-number",
            "interviewer_id": str(interview_interviewer.id),
            "scheduled_at": scheduled_time,
        },
        follow_redirects=False,
    )
    assert response.status_code == 400


@pytest.mark.asyncio
async def test_schedule_interview_invalid_interviewer_id(
    client: AsyncClient,
    interview_admin: User,
    interview_application: Application,
):
    """Scheduling with an invalid interviewer ID should return 400."""
    client.cookies.update(get_auth_cookie(interview_admin))
    scheduled_time = (datetime.utcnow() + timedelta(days=3)).strftime(
        "%Y-%m-%dT%H:%M"
    )
    response = await client.post(
        "/interviews",
        data={
            "application_id": str(interview_application.id),
            "interviewer_id": "invalid",
            "scheduled_at": scheduled_time,
        },
        follow_redirects=False,
    )
    assert response.status_code == 400


@pytest.mark.asyncio
async def test_schedule_interview_missing_scheduled_at(
    client: AsyncClient,
    interview_admin: User,
    interview_application: Application,
    interview_interviewer: User,
):
    """Scheduling without a date/time should return 400."""
    client.cookies.update(get_auth_cookie(interview_admin))
    response = await client.post(
        "/interviews",
        data={
            "application_id": str(interview_application.id),
            "interviewer_id": str(interview_interviewer.id),
            "scheduled_at": "",
        },
        follow_redirects=False,
    )
    assert response.status_code == 400


@pytest.mark.asyncio
async def test_schedule_interview_invalid_datetime_format(
    client: AsyncClient,
    interview_admin: User,
    interview_application: Application,
    interview_interviewer: User,
):
    """Scheduling with an invalid datetime format should return 400."""
    client.cookies.update(get_auth_cookie(interview_admin))
    response = await client.post(
        "/interviews",
        data={
            "application_id": str(interview_application.id),
            "interviewer_id": str(interview_interviewer.id),
            "scheduled_at": "not-a-date",
        },
        follow_redirects=False,
    )
    assert response.status_code == 400


@pytest.mark.asyncio
async def test_schedule_interview_nonexistent_application(
    client: AsyncClient,
    interview_admin: User,
    interview_interviewer: User,
):
    """Scheduling for a non-existent application should return 400."""
    client.cookies.update(get_auth_cookie(interview_admin))
    scheduled_time = (datetime.utcnow() + timedelta(days=3)).strftime(
        "%Y-%m-%dT%H:%M"
    )
    response = await client.post(
        "/interviews",
        data={
            "application_id": "99999",
            "interviewer_id": str(interview_interviewer.id),
            "scheduled_at": scheduled_time,
        },
        follow_redirects=False,
    )
    assert response.status_code == 400


@pytest.mark.asyncio
async def test_schedule_interview_nonexistent_interviewer(
    client: AsyncClient,
    interview_admin: User,
    interview_application: Application,
):
    """Scheduling with a non-existent interviewer should return 400."""
    client.cookies.update(get_auth_cookie(interview_admin))
    scheduled_time = (datetime.utcnow() + timedelta(days=3)).strftime(
        "%Y-%m-%dT%H:%M"
    )
    response = await client.post(
        "/interviews",
        data={
            "application_id": str(interview_application.id),
            "interviewer_id": "99999",
            "scheduled_at": scheduled_time,
        },
        follow_redirects=False,
    )
    assert response.status_code == 400


# ── Feedback Page Tests ───────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_feedback_page_accessible_by_assigned_interviewer(
    client: AsyncClient,
    interview_interviewer: User,
    scheduled_interview: Interview,
):
    """Assigned interviewer can access the feedback page."""
    client.cookies.update(get_auth_cookie(interview_interviewer))
    response = await client.get(
        f"/interviews/{scheduled_interview.id}/feedback",
        follow_redirects=False,
    )
    assert response.status_code == 200
    assert b"Feedback" in response.content


@pytest.mark.asyncio
async def test_feedback_page_accessible_by_admin(
    client: AsyncClient,
    interview_admin: User,
    scheduled_interview: Interview,
):
    """Admin can access the feedback page for any interview."""
    client.cookies.update(get_auth_cookie(interview_admin))
    response = await client.get(
        f"/interviews/{scheduled_interview.id}/feedback",
        follow_redirects=False,
    )
    assert response.status_code == 200
    assert b"Feedback" in response.content


@pytest.mark.asyncio
async def test_feedback_page_accessible_by_hiring_manager(
    client: AsyncClient,
    interview_hiring_manager: User,
    scheduled_interview: Interview,
):
    """Hiring manager can access the feedback page."""
    client.cookies.update(get_auth_cookie(interview_hiring_manager))
    response = await client.get(
        f"/interviews/{scheduled_interview.id}/feedback",
        follow_redirects=False,
    )
    assert response.status_code == 200


@pytest.mark.asyncio
async def test_feedback_page_denied_for_unassigned_interviewer(
    client: AsyncClient,
    db_session: AsyncSession,
    scheduled_interview: Interview,
):
    """An interviewer not assigned to the interview should be redirected."""
    other_interviewer = User(
        username="other_interviewer",
        email="other_interviewer@talentflow.local",
        hashed_password=hash_password("password123"),
        full_name="Other Interviewer",
        role="interviewer",
        is_active=1,
    )
    db_session.add(other_interviewer)
    await db_session.flush()
    await db_session.refresh(other_interviewer)

    client.cookies.update(get_auth_cookie(other_interviewer))
    response = await client.get(
        f"/interviews/{scheduled_interview.id}/feedback",
        follow_redirects=False,
    )
    assert response.status_code == 302
    assert "/interviews" in response.headers.get("location", "")


@pytest.mark.asyncio
async def test_feedback_page_nonexistent_interview(
    client: AsyncClient,
    interview_admin: User,
):
    """Accessing feedback for a non-existent interview should redirect."""
    client.cookies.update(get_auth_cookie(interview_admin))
    response = await client.get(
        "/interviews/99999/feedback",
        follow_redirects=False,
    )
    assert response.status_code == 302
    assert "/interviews" in response.headers.get("location", "")


@pytest.mark.asyncio
async def test_feedback_page_readonly_after_submission(
    client: AsyncClient,
    interview_interviewer: User,
    completed_interview: Interview,
):
    """Feedback page should be read-only after feedback has been submitted."""
    client.cookies.update(get_auth_cookie(interview_interviewer))
    response = await client.get(
        f"/interviews/{completed_interview.id}/feedback",
        follow_redirects=False,
    )
    assert response.status_code == 200
    assert b"Submitted" in response.content or b"submitted" in response.content


# ── Feedback Submission Tests ─────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_submit_feedback_success_by_interviewer(
    client: AsyncClient,
    interview_interviewer: User,
    scheduled_interview: Interview,
):
    """Assigned interviewer can submit feedback with valid rating and notes."""
    client.cookies.update(get_auth_cookie(interview_interviewer))
    response = await client.post(
        f"/interviews/{scheduled_interview.id}/feedback",
        data={
            "rating": "4",
            "feedback_notes": "Great candidate, strong problem-solving skills.",
        },
        follow_redirects=False,
    )
    assert response.status_code == 302
    assert "/interviews" in response.headers.get("location", "")


@pytest.mark.asyncio
async def test_submit_feedback_rating_1(
    client: AsyncClient,
    interview_interviewer: User,
    scheduled_interview: Interview,
):
    """Rating of 1 (minimum) should be accepted."""
    client.cookies.update(get_auth_cookie(interview_interviewer))
    response = await client.post(
        f"/interviews/{scheduled_interview.id}/feedback",
        data={
            "rating": "1",
            "feedback_notes": "Did not meet expectations.",
        },
        follow_redirects=False,
    )
    assert response.status_code == 302


@pytest.mark.asyncio
async def test_submit_feedback_rating_5(
    client: AsyncClient,
    interview_interviewer: User,
    scheduled_interview: Interview,
):
    """Rating of 5 (maximum) should be accepted."""
    client.cookies.update(get_auth_cookie(interview_interviewer))
    response = await client.post(
        f"/interviews/{scheduled_interview.id}/feedback",
        data={
            "rating": "5",
            "feedback_notes": "Exceptional candidate, highly recommend.",
        },
        follow_redirects=False,
    )
    assert response.status_code == 302


@pytest.mark.asyncio
async def test_submit_feedback_without_notes(
    client: AsyncClient,
    interview_interviewer: User,
    scheduled_interview: Interview,
):
    """Feedback can be submitted with rating only (notes are optional)."""
    client.cookies.update(get_auth_cookie(interview_interviewer))
    response = await client.post(
        f"/interviews/{scheduled_interview.id}/feedback",
        data={
            "rating": "3",
            "feedback_notes": "",
        },
        follow_redirects=False,
    )
    assert response.status_code == 302


@pytest.mark.asyncio
async def test_submit_feedback_invalid_rating_zero(
    client: AsyncClient,
    interview_interviewer: User,
    scheduled_interview: Interview,
):
    """Rating of 0 should be rejected (must be 1-5)."""
    client.cookies.update(get_auth_cookie(interview_interviewer))
    response = await client.post(
        f"/interviews/{scheduled_interview.id}/feedback",
        data={
            "rating": "0",
            "feedback_notes": "Invalid rating test.",
        },
        follow_redirects=False,
    )
    assert response.status_code == 400


@pytest.mark.asyncio
async def test_submit_feedback_invalid_rating_six(
    client: AsyncClient,
    interview_interviewer: User,
    scheduled_interview: Interview,
):
    """Rating of 6 should be rejected (must be 1-5)."""
    client.cookies.update(get_auth_cookie(interview_interviewer))
    response = await client.post(
        f"/interviews/{scheduled_interview.id}/feedback",
        data={
            "rating": "6",
            "feedback_notes": "Invalid rating test.",
        },
        follow_redirects=False,
    )
    assert response.status_code == 400


@pytest.mark.asyncio
async def test_submit_feedback_invalid_rating_non_numeric(
    client: AsyncClient,
    interview_interviewer: User,
    scheduled_interview: Interview,
):
    """Non-numeric rating should be rejected."""
    client.cookies.update(get_auth_cookie(interview_interviewer))
    response = await client.post(
        f"/interviews/{scheduled_interview.id}/feedback",
        data={
            "rating": "excellent",
            "feedback_notes": "Non-numeric rating test.",
        },
        follow_redirects=False,
    )
    assert response.status_code == 400


@pytest.mark.asyncio
async def test_submit_feedback_by_admin(
    client: AsyncClient,
    interview_admin: User,
    scheduled_interview: Interview,
):
    """Admin can submit feedback for any interview."""
    client.cookies.update(get_auth_cookie(interview_admin))
    response = await client.post(
        f"/interviews/{scheduled_interview.id}/feedback",
        data={
            "rating": "3",
            "feedback_notes": "Admin feedback submission.",
        },
        follow_redirects=False,
    )
    assert response.status_code == 302


@pytest.mark.asyncio
async def test_submit_feedback_by_hiring_manager(
    client: AsyncClient,
    interview_hiring_manager: User,
    scheduled_interview: Interview,
):
    """Hiring manager can submit feedback for interviews."""
    client.cookies.update(get_auth_cookie(interview_hiring_manager))
    response = await client.post(
        f"/interviews/{scheduled_interview.id}/feedback",
        data={
            "rating": "4",
            "feedback_notes": "Hiring manager feedback.",
        },
        follow_redirects=False,
    )
    assert response.status_code == 302


@pytest.mark.asyncio
async def test_submit_feedback_denied_for_unassigned_interviewer(
    client: AsyncClient,
    db_session: AsyncSession,
    scheduled_interview: Interview,
):
    """An interviewer not assigned to the interview cannot submit feedback."""
    other_interviewer = User(
        username="other_int_fb",
        email="other_int_fb@talentflow.local",
        hashed_password=hash_password("password123"),
        full_name="Other Interviewer FB",
        role="interviewer",
        is_active=1,
    )
    db_session.add(other_interviewer)
    await db_session.flush()
    await db_session.refresh(other_interviewer)

    client.cookies.update(get_auth_cookie(other_interviewer))
    response = await client.post(
        f"/interviews/{scheduled_interview.id}/feedback",
        data={
            "rating": "3",
            "feedback_notes": "Should not be allowed.",
        },
        follow_redirects=False,
    )
    # Should redirect since the user is not the assigned interviewer
    assert response.status_code == 302
    assert "/interviews" in response.headers.get("location", "")


@pytest.mark.asyncio
async def test_submit_feedback_nonexistent_interview(
    client: AsyncClient,
    interview_admin: User,
):
    """Submitting feedback for a non-existent interview should redirect."""
    client.cookies.update(get_auth_cookie(interview_admin))
    response = await client.post(
        "/interviews/99999/feedback",
        data={
            "rating": "3",
            "feedback_notes": "Non-existent interview.",
        },
        follow_redirects=False,
    )
    assert response.status_code == 302
    assert "/interviews" in response.headers.get("location", "")


# ── Feedback Immutability Tests ───────────────────────────────────────────────


@pytest.mark.asyncio
async def test_feedback_immutability_readonly_page(
    client: AsyncClient,
    interview_interviewer: User,
    completed_interview: Interview,
):
    """Once feedback is submitted, the page should show it as read-only."""
    client.cookies.update(get_auth_cookie(interview_interviewer))
    response = await client.get(
        f"/interviews/{completed_interview.id}/feedback",
        follow_redirects=False,
    )
    assert response.status_code == 200
    content = response.content.decode()
    # The page should indicate feedback has been submitted
    assert "submitted" in content.lower() or "Submitted" in content


@pytest.mark.asyncio
async def test_feedback_shows_existing_rating(
    client: AsyncClient,
    interview_admin: User,
    completed_interview: Interview,
):
    """Completed interview feedback page should display the existing rating."""
    client.cookies.update(get_auth_cookie(interview_admin))
    response = await client.get(
        f"/interviews/{completed_interview.id}/feedback",
        follow_redirects=False,
    )
    assert response.status_code == 200
    content = response.content.decode()
    assert "4" in content or "4/5" in content


@pytest.mark.asyncio
async def test_feedback_shows_existing_notes(
    client: AsyncClient,
    interview_admin: User,
    completed_interview: Interview,
):
    """Completed interview feedback page should display the existing notes."""
    client.cookies.update(get_auth_cookie(interview_admin))
    response = await client.get(
        f"/interviews/{completed_interview.id}/feedback",
        follow_redirects=False,
    )
    assert response.status_code == 200
    assert b"Strong candidate" in response.content


# ── RBAC Enforcement Tests ────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_schedule_requires_login(client: AsyncClient):
    """Unauthenticated users cannot access the schedule page."""
    response = await client.get("/interviews/schedule", follow_redirects=False)
    assert response.status_code == 401


@pytest.mark.asyncio
async def test_schedule_submit_requires_login(client: AsyncClient):
    """Unauthenticated users cannot submit a schedule request."""
    response = await client.post(
        "/interviews",
        data={
            "application_id": "1",
            "interviewer_id": "1",
            "scheduled_at": "2025-06-01T10:00",
        },
        follow_redirects=False,
    )
    assert response.status_code == 401


@pytest.mark.asyncio
async def test_feedback_page_requires_login(client: AsyncClient):
    """Unauthenticated users cannot access the feedback page."""
    response = await client.get(
        "/interviews/1/feedback", follow_redirects=False
    )
    assert response.status_code == 401


@pytest.mark.asyncio
async def test_feedback_submit_requires_login(client: AsyncClient):
    """Unauthenticated users cannot submit feedback."""
    response = await client.post(
        "/interviews/1/feedback",
        data={"rating": "3", "feedback_notes": "test"},
        follow_redirects=False,
    )
    assert response.status_code == 401


@pytest.mark.asyncio
async def test_viewer_cannot_submit_feedback(
    client: AsyncClient,
    interview_viewer: User,
    scheduled_interview: Interview,
):
    """Viewers should be redirected when trying to access feedback page."""
    client.cookies.update(get_auth_cookie(interview_viewer))
    response = await client.get(
        f"/interviews/{scheduled_interview.id}/feedback",
        follow_redirects=False,
    )
    # Viewer is not interviewer and not admin/hiring_manager, so redirected
    assert response.status_code == 302
    assert "/interviews" in response.headers.get("location", "")


@pytest.mark.asyncio
async def test_recruiter_cannot_access_feedback_page(
    client: AsyncClient,
    interview_recruiter: User,
    scheduled_interview: Interview,
):
    """Recruiters who are not the assigned interviewer should be redirected."""
    client.cookies.update(get_auth_cookie(interview_recruiter))
    response = await client.get(
        f"/interviews/{scheduled_interview.id}/feedback",
        follow_redirects=False,
    )
    # Recruiter is not interviewer and not admin/hiring_manager, so redirected
    assert response.status_code == 302
    assert "/interviews" in response.headers.get("location", "")


# ── Interview Redirect Tests ─────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_interviewer_feedback_redirects_to_my_interviews(
    client: AsyncClient,
    interview_interviewer: User,
    scheduled_interview: Interview,
):
    """After submitting feedback, interviewer should be redirected to /interviews/my."""
    client.cookies.update(get_auth_cookie(interview_interviewer))
    response = await client.post(
        f"/interviews/{scheduled_interview.id}/feedback",
        data={
            "rating": "4",
            "feedback_notes": "Good candidate.",
        },
        follow_redirects=False,
    )
    assert response.status_code == 302
    assert "/interviews/my" in response.headers.get("location", "")


@pytest.mark.asyncio
async def test_admin_feedback_redirects_to_interviews(
    client: AsyncClient,
    interview_admin: User,
    scheduled_interview: Interview,
):
    """After submitting feedback, admin should be redirected to /interviews."""
    client.cookies.update(get_auth_cookie(interview_admin))
    response = await client.post(
        f"/interviews/{scheduled_interview.id}/feedback",
        data={
            "rating": "3",
            "feedback_notes": "Admin review.",
        },
        follow_redirects=False,
    )
    assert response.status_code == 302
    location = response.headers.get("location", "")
    assert "/interviews" in location
    assert "/interviews/my" not in location


# ── Service Layer Tests ───────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_schedule_interview_service(
    db_session: AsyncSession,
    interview_application: Application,
    interview_interviewer: User,
    interview_admin: User,
):
    """Test the schedule_interview service function directly."""
    from app.services.interview_service import schedule_interview

    scheduled_time = datetime.utcnow() + timedelta(days=10)
    interview, error = await schedule_interview(
        db=db_session,
        application_id=interview_application.id,
        interviewer_id=interview_interviewer.id,
        scheduled_at=scheduled_time,
        user=interview_admin,
    )
    assert interview is not None
    assert error is None
    assert interview.application_id == interview_application.id
    assert interview.interviewer_id == interview_interviewer.id
    assert interview.scheduled_at == scheduled_time
    assert interview.rating is None
    assert interview.feedback_notes is None


@pytest.mark.asyncio
async def test_schedule_interview_service_permission_denied(
    db_session: AsyncSession,
    interview_application: Application,
    interview_interviewer: User,
):
    """Interviewer role should not be allowed to schedule via service."""
    from app.services.interview_service import schedule_interview

    scheduled_time = datetime.utcnow() + timedelta(days=10)
    interview, error = await schedule_interview(
        db=db_session,
        application_id=interview_application.id,
        interviewer_id=interview_interviewer.id,
        scheduled_at=scheduled_time,
        user=interview_interviewer,
    )
    assert interview is None
    assert error is not None
    assert "permission" in error.lower()


@pytest.mark.asyncio
async def test_submit_feedback_service(
    db_session: AsyncSession,
    scheduled_interview: Interview,
    interview_interviewer: User,
):
    """Test the submit_feedback service function directly."""
    from app.services.interview_service import submit_feedback

    updated, error = await submit_feedback(
        db=db_session,
        interview_id=scheduled_interview.id,
        rating=4,
        feedback_notes="Solid technical skills, good communication.",
        user=interview_interviewer,
    )
    assert updated is not None
    assert error is None
    assert updated.rating == 4
    assert updated.feedback_notes == "Solid technical skills, good communication."


@pytest.mark.asyncio
async def test_submit_feedback_service_invalid_rating_low(
    db_session: AsyncSession,
    scheduled_interview: Interview,
    interview_interviewer: User,
):
    """Rating below 1 should be rejected by the service."""
    from app.services.interview_service import submit_feedback

    updated, error = await submit_feedback(
        db=db_session,
        interview_id=scheduled_interview.id,
        rating=0,
        feedback_notes="Invalid.",
        user=interview_interviewer,
    )
    assert updated is None
    assert error is not None
    assert "1" in error and "5" in error


@pytest.mark.asyncio
async def test_submit_feedback_service_invalid_rating_high(
    db_session: AsyncSession,
    scheduled_interview: Interview,
    interview_interviewer: User,
):
    """Rating above 5 should be rejected by the service."""
    from app.services.interview_service import submit_feedback

    updated, error = await submit_feedback(
        db=db_session,
        interview_id=scheduled_interview.id,
        rating=6,
        feedback_notes="Invalid.",
        user=interview_interviewer,
    )
    assert updated is None
    assert error is not None
    assert "1" in error and "5" in error


@pytest.mark.asyncio
async def test_submit_feedback_service_permission_denied(
    db_session: AsyncSession,
    scheduled_interview: Interview,
    interview_viewer: User,
):
    """Viewer role should not be allowed to submit feedback via service."""
    from app.services.interview_service import submit_feedback

    updated, error = await submit_feedback(
        db=db_session,
        interview_id=scheduled_interview.id,
        rating=3,
        feedback_notes="Should fail.",
        user=interview_viewer,
    )
    assert updated is None
    assert error is not None
    assert "permission" in error.lower()


@pytest.mark.asyncio
async def test_submit_feedback_service_nonexistent_interview(
    db_session: AsyncSession,
    interview_admin: User,
):
    """Submitting feedback for a non-existent interview should fail."""
    from app.services.interview_service import submit_feedback

    updated, error = await submit_feedback(
        db=db_session,
        interview_id=99999,
        rating=3,
        feedback_notes="Non-existent.",
        user=interview_admin,
    )
    assert updated is None
    assert error is not None
    assert "not found" in error.lower()


@pytest.mark.asyncio
async def test_get_interview_by_id_service(
    db_session: AsyncSession,
    scheduled_interview: Interview,
):
    """Test fetching an interview by ID via service."""
    from app.services.interview_service import get_interview_by_id

    interview = await get_interview_by_id(db_session, scheduled_interview.id)
    assert interview is not None
    assert interview.id == scheduled_interview.id


@pytest.mark.asyncio
async def test_get_interview_by_id_nonexistent(
    db_session: AsyncSession,
):
    """Fetching a non-existent interview should return None."""
    from app.services.interview_service import get_interview_by_id

    interview = await get_interview_by_id(db_session, 99999)
    assert interview is None


@pytest.mark.asyncio
async def test_list_my_interviews_service(
    db_session: AsyncSession,
    interview_interviewer: User,
    scheduled_interview: Interview,
):
    """Test listing interviews for a specific interviewer."""
    from app.services.interview_service import list_my_interviews

    interviews = await list_my_interviews(
        db=db_session,
        user=interview_interviewer,
        upcoming_only=False,
    )
    assert len(interviews) >= 1
    assert any(i.id == scheduled_interview.id for i in interviews)


@pytest.mark.asyncio
async def test_list_my_interviews_upcoming_only(
    db_session: AsyncSession,
    interview_interviewer: User,
    scheduled_interview: Interview,
):
    """Upcoming-only filter should return only future interviews."""
    from app.services.interview_service import list_my_interviews

    interviews = await list_my_interviews(
        db=db_session,
        user=interview_interviewer,
        upcoming_only=True,
    )
    now = datetime.utcnow()
    for interview in interviews:
        assert interview.scheduled_at >= now


@pytest.mark.asyncio
async def test_get_all_interviewers_service(
    db_session: AsyncSession,
    interview_interviewer: User,
    interview_admin: User,
):
    """Test fetching all active users as potential interviewers."""
    from app.services.interview_service import get_all_interviewers

    interviewers = await get_all_interviewers(db=db_session)
    assert len(interviewers) >= 2
    usernames = [u.username for u in interviewers]
    assert interview_interviewer.username in usernames
    assert interview_admin.username in usernames


@pytest.mark.asyncio
async def test_get_schedulable_applications_service(
    db_session: AsyncSession,
    interview_admin: User,
    interview_application: Application,
):
    """Test fetching applications eligible for interview scheduling."""
    from app.services.interview_service import get_schedulable_applications

    applications = await get_schedulable_applications(
        db=db_session,
        user=interview_admin,
    )
    assert len(applications) >= 1
    assert any(a.id == interview_application.id for a in applications)


@pytest.mark.asyncio
async def test_count_pending_feedback_service(
    db_session: AsyncSession,
    interview_interviewer: User,
    scheduled_interview: Interview,
):
    """Test counting interviews pending feedback for an interviewer."""
    from app.services.interview_service import count_pending_feedback

    count = await count_pending_feedback(
        db=db_session,
        user=interview_interviewer,
    )
    assert count >= 1


@pytest.mark.asyncio
async def test_count_pending_feedback_zero_after_submission(
    db_session: AsyncSession,
    interview_interviewer: User,
    scheduled_interview: Interview,
):
    """After submitting feedback, pending count should decrease."""
    from app.services.interview_service import count_pending_feedback, submit_feedback

    count_before = await count_pending_feedback(
        db=db_session,
        user=interview_interviewer,
    )

    await submit_feedback(
        db=db_session,
        interview_id=scheduled_interview.id,
        rating=4,
        feedback_notes="Done.",
        user=interview_interviewer,
    )

    count_after = await count_pending_feedback(
        db=db_session,
        user=interview_interviewer,
    )
    assert count_after < count_before
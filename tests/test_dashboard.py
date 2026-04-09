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


@pytest.mark.asyncio
async def test_dashboard_requires_authentication(client: AsyncClient):
    """Dashboard should redirect or return 401 for unauthenticated users."""
    response = await client.get("/dashboard", follow_redirects=False)
    assert response.status_code in (401, 302, 303)


@pytest.mark.asyncio
async def test_dashboard_admin_access(
    authenticated_admin_client: AsyncClient,
    admin_user: User,
):
    """Admin user should see the dashboard with pipeline overview and audit log sections."""
    response = await authenticated_admin_client.get("/dashboard")
    assert response.status_code == 200
    content = response.text
    assert "Dashboard" in content
    assert "Open Jobs" in content
    assert "Total Candidates" in content
    assert "Active Applications" in content
    assert "Upcoming Interviews" in content
    assert "Pipeline Overview" in content
    assert "Recent Activity" in content


@pytest.mark.asyncio
async def test_dashboard_recruiter_access(
    client: AsyncClient,
    recruiter_user: User,
):
    """Recruiter user should see the dashboard with pipeline overview and quick actions."""
    client.cookies.update(get_auth_cookie(recruiter_user))
    response = await client.get("/dashboard")
    assert response.status_code == 200
    content = response.text
    assert "Dashboard" in content
    assert "Open Jobs" in content
    assert "Total Candidates" in content
    assert "Active Applications" in content
    assert "Pipeline Overview" in content
    assert "Quick Actions" in content
    assert "Create Job Posting" in content
    assert "Add Candidate" in content


@pytest.mark.asyncio
async def test_dashboard_hiring_manager_access(
    client: AsyncClient,
    hiring_manager_user: User,
):
    """Hiring manager should see their job requisitions and interview status."""
    client.cookies.update(get_auth_cookie(hiring_manager_user))
    response = await client.get("/dashboard")
    assert response.status_code == 200
    content = response.text
    assert "Dashboard" in content
    assert "Open Jobs" in content
    assert "My Job Requisitions" in content
    assert "Interview Status" in content


@pytest.mark.asyncio
async def test_dashboard_interviewer_access(
    client: AsyncClient,
    interviewer_user: User,
):
    """Interviewer should see upcoming interviews and pending feedback sections."""
    client.cookies.update(get_auth_cookie(interviewer_user))
    response = await client.get("/dashboard")
    assert response.status_code == 200
    content = response.text
    assert "Dashboard" in content
    assert "Open Jobs" in content
    assert "My Upcoming Interviews" in content


@pytest.mark.asyncio
async def test_dashboard_viewer_access(
    client: AsyncClient,
    viewer_user: User,
):
    """Viewer should see basic stats and browse links."""
    client.cookies.update(get_auth_cookie(viewer_user))
    response = await client.get("/dashboard")
    assert response.status_code == 200
    content = response.text
    assert "Dashboard" in content
    assert "Open Jobs" in content
    assert "Browse" in content
    assert "Job Postings" in content
    assert "Candidates" in content
    assert "Applications" in content


@pytest.mark.asyncio
async def test_dashboard_admin_stats_reflect_data(
    authenticated_admin_client: AsyncClient,
    admin_user: User,
    db_session: AsyncSession,
    test_department: Department,
):
    """Admin dashboard stats should reflect actual data counts."""
    job1 = JobPosting(
        title="Published Job 1",
        description="Description 1",
        status="Published",
        department_id=test_department.id,
        hiring_manager_id=admin_user.id,
        location="Remote",
        type="Full-Time",
    )
    job2 = JobPosting(
        title="Published Job 2",
        description="Description 2",
        status="Published",
        department_id=test_department.id,
        hiring_manager_id=admin_user.id,
        location="NYC",
        type="Full-Time",
    )
    job3 = JobPosting(
        title="Draft Job",
        description="Description 3",
        status="Draft",
        department_id=test_department.id,
        hiring_manager_id=admin_user.id,
        location="Remote",
        type="Full-Time",
    )
    db_session.add_all([job1, job2, job3])
    await db_session.flush()

    candidate1 = Candidate(
        first_name="Alice",
        last_name="Test",
        email="alice.test@example.com",
    )
    candidate2 = Candidate(
        first_name="Bob",
        last_name="Test",
        email="bob.test@example.com",
    )
    db_session.add_all([candidate1, candidate2])
    await db_session.flush()

    app1 = Application(
        candidate_id=candidate1.id,
        job_id=job1.id,
        stage="Applied",
    )
    app2 = Application(
        candidate_id=candidate2.id,
        job_id=job2.id,
        stage="Screening",
    )
    db_session.add_all([app1, app2])
    await db_session.flush()
    await db_session.commit()

    response = await authenticated_admin_client.get("/dashboard")
    assert response.status_code == 200
    content = response.text

    # Should show 2 open (published) jobs
    assert ">2<" in content.replace(" ", "") or "2</p>" in content

    # Should show 2 candidates
    assert "Total Candidates" in content

    # Should show 2 active applications
    assert "Active Applications" in content

    # Pipeline stages should be visible
    assert "Applied" in content
    assert "Screening" in content


@pytest.mark.asyncio
async def test_dashboard_admin_recent_applications(
    authenticated_admin_client: AsyncClient,
    admin_user: User,
    db_session: AsyncSession,
    test_department: Department,
):
    """Admin dashboard should show recent applications."""
    job = JobPosting(
        title="Test Job for Recent Apps",
        description="Description",
        status="Published",
        department_id=test_department.id,
        hiring_manager_id=admin_user.id,
        location="Remote",
        type="Full-Time",
    )
    db_session.add(job)
    await db_session.flush()

    candidate = Candidate(
        first_name="Recent",
        last_name="Applicant",
        email="recent.applicant@example.com",
    )
    db_session.add(candidate)
    await db_session.flush()

    application = Application(
        candidate_id=candidate.id,
        job_id=job.id,
        stage="Applied",
    )
    db_session.add(application)
    await db_session.flush()
    await db_session.commit()

    response = await authenticated_admin_client.get("/dashboard")
    assert response.status_code == 200
    content = response.text
    assert "Recent Applications" in content
    assert "Recent Applicant" in content
    assert "Test Job for Recent Apps" in content


@pytest.mark.asyncio
async def test_dashboard_hiring_manager_sees_own_jobs(
    client: AsyncClient,
    db_session: AsyncSession,
    test_department: Department,
):
    """Hiring manager should only see their own job requisitions on the dashboard."""
    hm_user = User(
        username="hm_dashboard_test",
        email="hm_dashboard_test@talentflow.local",
        hashed_password=hash_password("password123"),
        full_name="HM Dashboard Test",
        role="hiring_manager",
        is_active=1,
    )
    db_session.add(hm_user)
    await db_session.flush()

    other_user = User(
        username="other_hm_test",
        email="other_hm_test@talentflow.local",
        hashed_password=hash_password("password123"),
        full_name="Other HM Test",
        role="hiring_manager",
        is_active=1,
    )
    db_session.add(other_user)
    await db_session.flush()

    my_job = JobPosting(
        title="My HM Job",
        description="My job description",
        status="Published",
        department_id=test_department.id,
        hiring_manager_id=hm_user.id,
        location="Remote",
        type="Full-Time",
    )
    other_job = JobPosting(
        title="Other HM Job",
        description="Other job description",
        status="Published",
        department_id=test_department.id,
        hiring_manager_id=other_user.id,
        location="NYC",
        type="Full-Time",
    )
    db_session.add_all([my_job, other_job])
    await db_session.flush()
    await db_session.commit()

    client.cookies.update(get_auth_cookie(hm_user))
    response = await client.get("/dashboard")
    assert response.status_code == 200
    content = response.text
    assert "My HM Job" in content
    assert "Other HM Job" not in content


@pytest.mark.asyncio
async def test_dashboard_interviewer_sees_upcoming_interviews(
    client: AsyncClient,
    db_session: AsyncSession,
    test_department: Department,
):
    """Interviewer should see their upcoming interviews on the dashboard."""
    admin = User(
        username="admin_for_iv_test",
        email="admin_for_iv_test@talentflow.local",
        hashed_password=hash_password("password123"),
        full_name="Admin IV Test",
        role="admin",
        is_active=1,
    )
    db_session.add(admin)
    await db_session.flush()

    interviewer = User(
        username="iv_dashboard_test",
        email="iv_dashboard_test@talentflow.local",
        hashed_password=hash_password("password123"),
        full_name="Interviewer Dashboard Test",
        role="interviewer",
        is_active=1,
    )
    db_session.add(interviewer)
    await db_session.flush()

    job = JobPosting(
        title="Job for IV Dashboard",
        description="Description",
        status="Published",
        department_id=test_department.id,
        hiring_manager_id=admin.id,
        location="Remote",
        type="Full-Time",
    )
    db_session.add(job)
    await db_session.flush()

    candidate = Candidate(
        first_name="Interview",
        last_name="Candidate",
        email="interview.candidate@example.com",
    )
    db_session.add(candidate)
    await db_session.flush()

    application = Application(
        candidate_id=candidate.id,
        job_id=job.id,
        stage="Interviewing",
    )
    db_session.add(application)
    await db_session.flush()

    interview = Interview(
        application_id=application.id,
        interviewer_id=interviewer.id,
        scheduled_at=datetime.utcnow() + timedelta(days=2),
    )
    db_session.add(interview)
    await db_session.flush()
    await db_session.commit()

    client.cookies.update(get_auth_cookie(interviewer))
    response = await client.get("/dashboard")
    assert response.status_code == 200
    content = response.text
    assert "My Upcoming Interviews" in content
    assert "Interview Candidate" in content


@pytest.mark.asyncio
async def test_dashboard_interviewer_pending_feedback_alert(
    client: AsyncClient,
    db_session: AsyncSession,
    test_department: Department,
):
    """Interviewer should see pending feedback alert when they have unrated interviews."""
    admin = User(
        username="admin_for_fb_test",
        email="admin_for_fb_test@talentflow.local",
        hashed_password=hash_password("password123"),
        full_name="Admin FB Test",
        role="admin",
        is_active=1,
    )
    db_session.add(admin)
    await db_session.flush()

    interviewer = User(
        username="iv_feedback_test",
        email="iv_feedback_test@talentflow.local",
        hashed_password=hash_password("password123"),
        full_name="Interviewer Feedback Test",
        role="interviewer",
        is_active=1,
    )
    db_session.add(interviewer)
    await db_session.flush()

    job = JobPosting(
        title="Job for Feedback Test",
        description="Description",
        status="Published",
        department_id=test_department.id,
        hiring_manager_id=admin.id,
        location="Remote",
        type="Full-Time",
    )
    db_session.add(job)
    await db_session.flush()

    candidate = Candidate(
        first_name="Feedback",
        last_name="Pending",
        email="feedback.pending@example.com",
    )
    db_session.add(candidate)
    await db_session.flush()

    application = Application(
        candidate_id=candidate.id,
        job_id=job.id,
        stage="Interviewing",
    )
    db_session.add(application)
    await db_session.flush()

    # Interview without rating (pending feedback)
    interview = Interview(
        application_id=application.id,
        interviewer_id=interviewer.id,
        scheduled_at=datetime.utcnow() + timedelta(days=1),
        rating=None,
        feedback_notes=None,
    )
    db_session.add(interview)
    await db_session.flush()
    await db_session.commit()

    client.cookies.update(get_auth_cookie(interviewer))
    response = await client.get("/dashboard")
    assert response.status_code == 200
    content = response.text
    assert "Feedback Required" in content


@pytest.mark.asyncio
async def test_dashboard_interviewer_no_pending_feedback(
    client: AsyncClient,
    db_session: AsyncSession,
    test_department: Department,
):
    """Interviewer should not see pending feedback alert when all interviews are rated."""
    admin = User(
        username="admin_no_fb_test",
        email="admin_no_fb_test@talentflow.local",
        hashed_password=hash_password("password123"),
        full_name="Admin No FB Test",
        role="admin",
        is_active=1,
    )
    db_session.add(admin)
    await db_session.flush()

    interviewer = User(
        username="iv_no_feedback_test",
        email="iv_no_feedback_test@talentflow.local",
        hashed_password=hash_password("password123"),
        full_name="Interviewer No Feedback Test",
        role="interviewer",
        is_active=1,
    )
    db_session.add(interviewer)
    await db_session.flush()

    job = JobPosting(
        title="Job for No Feedback Test",
        description="Description",
        status="Published",
        department_id=test_department.id,
        hiring_manager_id=admin.id,
        location="Remote",
        type="Full-Time",
    )
    db_session.add(job)
    await db_session.flush()

    candidate = Candidate(
        first_name="Rated",
        last_name="Candidate",
        email="rated.candidate@example.com",
    )
    db_session.add(candidate)
    await db_session.flush()

    application = Application(
        candidate_id=candidate.id,
        job_id=job.id,
        stage="Interviewing",
    )
    db_session.add(application)
    await db_session.flush()

    # Interview with rating (feedback submitted)
    interview = Interview(
        application_id=application.id,
        interviewer_id=interviewer.id,
        scheduled_at=datetime.utcnow() + timedelta(days=1),
        rating=4,
        feedback_notes="Good candidate",
    )
    db_session.add(interview)
    await db_session.flush()
    await db_session.commit()

    client.cookies.update(get_auth_cookie(interviewer))
    response = await client.get("/dashboard")
    assert response.status_code == 200
    content = response.text
    assert "Feedback Required" not in content


@pytest.mark.asyncio
async def test_dashboard_admin_pipeline_stage_counts(
    authenticated_admin_client: AsyncClient,
    admin_user: User,
    db_session: AsyncSession,
    test_department: Department,
):
    """Admin dashboard should display pipeline stage counts correctly."""
    job = JobPosting(
        title="Pipeline Count Job",
        description="Description",
        status="Published",
        department_id=test_department.id,
        hiring_manager_id=admin_user.id,
        location="Remote",
        type="Full-Time",
    )
    db_session.add(job)
    await db_session.flush()

    stages_to_create = ["Applied", "Applied", "Screening", "Interviewing", "Offered", "Hired", "Rejected"]
    for i, stage in enumerate(stages_to_create):
        candidate = Candidate(
            first_name=f"Pipeline{i}",
            last_name="Test",
            email=f"pipeline{i}@example.com",
        )
        db_session.add(candidate)
        await db_session.flush()

        app = Application(
            candidate_id=candidate.id,
            job_id=job.id,
            stage=stage,
        )
        db_session.add(app)
        await db_session.flush()

    await db_session.commit()

    response = await authenticated_admin_client.get("/dashboard")
    assert response.status_code == 200
    content = response.text

    # All pipeline stages should be present
    assert "Applied" in content
    assert "Screening" in content
    assert "Interviewing" in content
    assert "Offered" in content
    assert "Hired" in content
    assert "Rejected" in content


@pytest.mark.asyncio
async def test_dashboard_hiring_manager_interview_status(
    client: AsyncClient,
    db_session: AsyncSession,
    test_department: Department,
):
    """Hiring manager should see interview status for their jobs."""
    hm = User(
        username="hm_iv_status_test",
        email="hm_iv_status_test@talentflow.local",
        hashed_password=hash_password("password123"),
        full_name="HM IV Status Test",
        role="hiring_manager",
        is_active=1,
    )
    db_session.add(hm)
    await db_session.flush()

    interviewer = User(
        username="iv_for_hm_test",
        email="iv_for_hm_test@talentflow.local",
        hashed_password=hash_password("password123"),
        full_name="IV for HM Test",
        role="interviewer",
        is_active=1,
    )
    db_session.add(interviewer)
    await db_session.flush()

    job = JobPosting(
        title="HM Interview Status Job",
        description="Description",
        status="Published",
        department_id=test_department.id,
        hiring_manager_id=hm.id,
        location="Remote",
        type="Full-Time",
    )
    db_session.add(job)
    await db_session.flush()

    candidate = Candidate(
        first_name="HMInterview",
        last_name="StatusCandidate",
        email="hm.interview.status@example.com",
    )
    db_session.add(candidate)
    await db_session.flush()

    application = Application(
        candidate_id=candidate.id,
        job_id=job.id,
        stage="Interviewing",
    )
    db_session.add(application)
    await db_session.flush()

    interview = Interview(
        application_id=application.id,
        interviewer_id=interviewer.id,
        scheduled_at=datetime.utcnow() + timedelta(days=5),
    )
    db_session.add(interview)
    await db_session.flush()
    await db_session.commit()

    client.cookies.update(get_auth_cookie(hm))
    response = await client.get("/dashboard")
    assert response.status_code == 200
    content = response.text
    assert "Interview Status" in content
    assert "HMInterview" in content
    assert "StatusCandidate" in content


@pytest.mark.asyncio
async def test_dashboard_empty_state_admin(
    authenticated_admin_client: AsyncClient,
    admin_user: User,
):
    """Admin dashboard should render correctly with no data."""
    response = await authenticated_admin_client.get("/dashboard")
    assert response.status_code == 200
    content = response.text
    assert "Dashboard" in content
    assert "0" in content  # Stats should show zeros


@pytest.mark.asyncio
async def test_dashboard_empty_state_interviewer(
    client: AsyncClient,
    interviewer_user: User,
):
    """Interviewer dashboard should render correctly with no interviews."""
    client.cookies.update(get_auth_cookie(interviewer_user))
    response = await client.get("/dashboard")
    assert response.status_code == 200
    content = response.text
    assert "Dashboard" in content
    assert "No upcoming interviews scheduled" in content


@pytest.mark.asyncio
async def test_dashboard_welcome_message(
    authenticated_admin_client: AsyncClient,
    admin_user: User,
):
    """Dashboard should display a welcome message with the user's email."""
    response = await authenticated_admin_client.get("/dashboard")
    assert response.status_code == 200
    content = response.text
    assert "Welcome back" in content
    assert admin_user.email in content


@pytest.mark.asyncio
async def test_dashboard_hiring_manager_active_applications_scoped(
    client: AsyncClient,
    db_session: AsyncSession,
    test_department: Department,
):
    """Hiring manager's active application count should only include their jobs."""
    hm1 = User(
        username="hm_scope_test1",
        email="hm_scope_test1@talentflow.local",
        hashed_password=hash_password("password123"),
        full_name="HM Scope Test 1",
        role="hiring_manager",
        is_active=1,
    )
    hm2 = User(
        username="hm_scope_test2",
        email="hm_scope_test2@talentflow.local",
        hashed_password=hash_password("password123"),
        full_name="HM Scope Test 2",
        role="hiring_manager",
        is_active=1,
    )
    db_session.add_all([hm1, hm2])
    await db_session.flush()

    job_hm1 = JobPosting(
        title="HM1 Scoped Job",
        description="Description",
        status="Published",
        department_id=test_department.id,
        hiring_manager_id=hm1.id,
        location="Remote",
        type="Full-Time",
    )
    job_hm2 = JobPosting(
        title="HM2 Scoped Job",
        description="Description",
        status="Published",
        department_id=test_department.id,
        hiring_manager_id=hm2.id,
        location="Remote",
        type="Full-Time",
    )
    db_session.add_all([job_hm1, job_hm2])
    await db_session.flush()

    # Create candidates and applications for both jobs
    for i in range(3):
        c = Candidate(
            first_name=f"HM1Cand{i}",
            last_name="Test",
            email=f"hm1cand{i}@example.com",
        )
        db_session.add(c)
        await db_session.flush()
        app = Application(candidate_id=c.id, job_id=job_hm1.id, stage="Applied")
        db_session.add(app)

    for i in range(5):
        c = Candidate(
            first_name=f"HM2Cand{i}",
            last_name="Test",
            email=f"hm2cand{i}@example.com",
        )
        db_session.add(c)
        await db_session.flush()
        app = Application(candidate_id=c.id, job_id=job_hm2.id, stage="Screening")
        db_session.add(app)

    await db_session.flush()
    await db_session.commit()

    # HM1 should see only their 3 applications
    client.cookies.update(get_auth_cookie(hm1))
    response = await client.get("/dashboard")
    assert response.status_code == 200
    content = response.text
    assert "My Job Requisitions" in content
    assert "HM1 Scoped Job" in content
    assert "HM2 Scoped Job" not in content
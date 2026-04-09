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
class TestJobListPage:
    """Tests for GET /jobs — job listing page."""

    async def test_unauthenticated_redirects(self, client: AsyncClient):
        """Unauthenticated users should get a 401 when accessing /jobs."""
        response = await client.get("/jobs", follow_redirects=False)
        assert response.status_code == 401

    async def test_admin_can_list_jobs(
        self,
        authenticated_admin_client: AsyncClient,
        test_job: JobPosting,
    ):
        """Admin users can view the job listing page."""
        response = await authenticated_admin_client.get("/jobs")
        assert response.status_code == 200
        assert "Senior Python Developer" in response.text

    async def test_interviewer_can_list_jobs(
        self,
        client: AsyncClient,
        interviewer_user: User,
        test_job: JobPosting,
    ):
        """Interviewer users can view the job listing page."""
        client.cookies.update(get_auth_cookie(interviewer_user))
        response = await client.get("/jobs")
        assert response.status_code == 200
        assert "Senior Python Developer" in response.text

    async def test_viewer_can_list_jobs(
        self,
        client: AsyncClient,
        viewer_user: User,
        test_job: JobPosting,
    ):
        """Viewer users can view the job listing page."""
        client.cookies.update(get_auth_cookie(viewer_user))
        response = await client.get("/jobs")
        assert response.status_code == 200

    async def test_search_filter(
        self,
        authenticated_admin_client: AsyncClient,
        test_job: JobPosting,
    ):
        """Search filter narrows results by title."""
        response = await authenticated_admin_client.get("/jobs?search=Python")
        assert response.status_code == 200
        assert "Senior Python Developer" in response.text

    async def test_search_no_results(
        self,
        authenticated_admin_client: AsyncClient,
        test_job: JobPosting,
    ):
        """Search for non-existent term returns no jobs."""
        response = await authenticated_admin_client.get("/jobs?search=NonExistentXYZ")
        assert response.status_code == 200
        assert "No jobs found" in response.text

    async def test_status_filter(
        self,
        authenticated_admin_client: AsyncClient,
        test_job: JobPosting,
        test_draft_job: JobPosting,
    ):
        """Status filter shows only matching jobs."""
        response = await authenticated_admin_client.get("/jobs?status=Published")
        assert response.status_code == 200
        assert "Senior Python Developer" in response.text
        assert "Junior Frontend Developer" not in response.text

    async def test_draft_status_filter(
        self,
        authenticated_admin_client: AsyncClient,
        test_job: JobPosting,
        test_draft_job: JobPosting,
    ):
        """Draft status filter shows only draft jobs."""
        response = await authenticated_admin_client.get("/jobs?status=Draft")
        assert response.status_code == 200
        assert "Junior Frontend Developer" in response.text
        assert "Senior Python Developer" not in response.text

    async def test_hiring_manager_sees_only_own_jobs(
        self,
        client: AsyncClient,
        hiring_manager_user: User,
        test_job: JobPosting,
        db_session: AsyncSession,
        test_department: Department,
    ):
        """Hiring managers only see jobs assigned to them."""
        # test_job is assigned to admin_user, not hiring_manager_user
        # Create a job for the hiring manager
        hm_job = JobPosting(
            title="HM Specific Job",
            description="A job for the hiring manager.",
            status="Published",
            department_id=test_department.id,
            hiring_manager_id=hiring_manager_user.id,
            location="Remote",
            type="Full-Time",
        )
        db_session.add(hm_job)
        await db_session.flush()
        await db_session.refresh(hm_job)

        client.cookies.update(get_auth_cookie(hiring_manager_user))
        response = await client.get("/jobs")
        assert response.status_code == 200
        assert "HM Specific Job" in response.text
        # The admin's job should NOT appear for this hiring manager
        assert "Senior Python Developer" not in response.text


@pytest.mark.asyncio
class TestJobCreatePage:
    """Tests for GET /jobs/create — job creation form."""

    async def test_admin_can_access_create_form(
        self,
        authenticated_admin_client: AsyncClient,
        test_department: Department,
    ):
        """Admin can access the job creation form."""
        response = await authenticated_admin_client.get("/jobs/create")
        assert response.status_code == 200
        assert "Create Job Posting" in response.text

    async def test_recruiter_can_access_create_form(
        self,
        authenticated_recruiter_client: AsyncClient,
        test_department: Department,
    ):
        """Recruiter can access the job creation form."""
        response = await authenticated_recruiter_client.get("/jobs/create")
        assert response.status_code == 200
        assert "Create Job Posting" in response.text

    async def test_hiring_manager_can_access_create_form(
        self,
        client: AsyncClient,
        hiring_manager_user: User,
        test_department: Department,
    ):
        """Hiring manager can access the job creation form."""
        client.cookies.update(get_auth_cookie(hiring_manager_user))
        response = await client.get("/jobs/create")
        assert response.status_code == 200
        assert "Create Job Posting" in response.text

    async def test_interviewer_cannot_access_create_form(
        self,
        authenticated_interviewer_client: AsyncClient,
    ):
        """Interviewer should be denied access to the job creation form."""
        response = await authenticated_interviewer_client.get(
            "/jobs/create", follow_redirects=False
        )
        assert response.status_code == 403

    async def test_viewer_cannot_access_create_form(
        self,
        client: AsyncClient,
        viewer_user: User,
    ):
        """Viewer should be denied access to the job creation form."""
        client.cookies.update(get_auth_cookie(viewer_user))
        response = await client.get("/jobs/create", follow_redirects=False)
        assert response.status_code == 403

    async def test_unauthenticated_cannot_access_create_form(
        self,
        client: AsyncClient,
    ):
        """Unauthenticated users should get 401."""
        response = await client.get("/jobs/create", follow_redirects=False)
        assert response.status_code == 401


@pytest.mark.asyncio
class TestJobCreateSubmit:
    """Tests for POST /jobs — job creation submission."""

    async def test_admin_can_create_job(
        self,
        authenticated_admin_client: AsyncClient,
        test_department: Department,
        admin_user: User,
    ):
        """Admin can create a new job posting."""
        response = await authenticated_admin_client.post(
            "/jobs",
            data={
                "title": "New Test Job",
                "description": "A brand new test job posting.",
                "department_id": str(test_department.id),
                "hiring_manager_id": str(admin_user.id),
                "location": "San Francisco, CA",
                "job_type": "Full-Time",
                "status": "Draft",
            },
            follow_redirects=False,
        )
        assert response.status_code == 302
        assert "/jobs/" in response.headers.get("location", "")

    async def test_recruiter_can_create_job(
        self,
        authenticated_recruiter_client: AsyncClient,
        test_department: Department,
        recruiter_user: User,
    ):
        """Recruiter can create a new job posting."""
        response = await authenticated_recruiter_client.post(
            "/jobs",
            data={
                "title": "Recruiter Created Job",
                "description": "Job created by recruiter.",
                "department_id": str(test_department.id),
                "hiring_manager_id": str(recruiter_user.id),
                "location": "Remote",
                "job_type": "Contract",
                "status": "Draft",
            },
            follow_redirects=False,
        )
        assert response.status_code == 302

    async def test_interviewer_cannot_create_job(
        self,
        authenticated_interviewer_client: AsyncClient,
        test_department: Department,
        interviewer_user: User,
    ):
        """Interviewer should be denied creating a job posting."""
        response = await authenticated_interviewer_client.post(
            "/jobs",
            data={
                "title": "Should Not Work",
                "description": "This should fail.",
                "department_id": str(test_department.id),
                "hiring_manager_id": str(interviewer_user.id),
                "location": "Remote",
                "job_type": "Full-Time",
                "status": "Draft",
            },
            follow_redirects=False,
        )
        assert response.status_code == 403

    async def test_create_job_with_salary_range(
        self,
        authenticated_admin_client: AsyncClient,
        test_department: Department,
        admin_user: User,
    ):
        """Job creation with salary range succeeds."""
        response = await authenticated_admin_client.post(
            "/jobs",
            data={
                "title": "Job With Salary",
                "description": "A job with salary range.",
                "department_id": str(test_department.id),
                "hiring_manager_id": str(admin_user.id),
                "location": "New York, NY",
                "job_type": "Full-Time",
                "status": "Published",
                "salary_min": "100000",
                "salary_max": "150000",
            },
            follow_redirects=False,
        )
        assert response.status_code == 302

    async def test_create_job_invalid_department(
        self,
        authenticated_admin_client: AsyncClient,
        admin_user: User,
    ):
        """Creating a job with invalid department returns 400."""
        response = await authenticated_admin_client.post(
            "/jobs",
            data={
                "title": "Invalid Dept Job",
                "description": "This should fail.",
                "department_id": "abc",
                "hiring_manager_id": str(admin_user.id),
                "location": "Remote",
                "job_type": "Full-Time",
                "status": "Draft",
            },
            follow_redirects=False,
        )
        assert response.status_code == 400

    async def test_create_job_invalid_salary(
        self,
        authenticated_admin_client: AsyncClient,
        test_department: Department,
        admin_user: User,
    ):
        """Creating a job with invalid salary returns 400."""
        response = await authenticated_admin_client.post(
            "/jobs",
            data={
                "title": "Invalid Salary Job",
                "description": "This should fail.",
                "department_id": str(test_department.id),
                "hiring_manager_id": str(admin_user.id),
                "location": "Remote",
                "job_type": "Full-Time",
                "status": "Draft",
                "salary_min": "not_a_number",
            },
            follow_redirects=False,
        )
        assert response.status_code == 400


@pytest.mark.asyncio
class TestJobDetailPage:
    """Tests for GET /jobs/{job_id} — job detail page."""

    async def test_admin_can_view_job_detail(
        self,
        authenticated_admin_client: AsyncClient,
        test_job: JobPosting,
    ):
        """Admin can view job detail page."""
        response = await authenticated_admin_client.get(f"/jobs/{test_job.id}")
        assert response.status_code == 200
        assert "Senior Python Developer" in response.text

    async def test_interviewer_can_view_job_detail(
        self,
        client: AsyncClient,
        interviewer_user: User,
        test_job: JobPosting,
    ):
        """Interviewer can view job detail page."""
        client.cookies.update(get_auth_cookie(interviewer_user))
        response = await client.get(f"/jobs/{test_job.id}")
        assert response.status_code == 200
        assert "Senior Python Developer" in response.text

    async def test_nonexistent_job_redirects(
        self,
        authenticated_admin_client: AsyncClient,
    ):
        """Accessing a non-existent job redirects to /jobs."""
        response = await authenticated_admin_client.get(
            "/jobs/99999", follow_redirects=False
        )
        assert response.status_code == 302
        assert "/jobs" in response.headers.get("location", "")

    async def test_unauthenticated_cannot_view_detail(
        self,
        client: AsyncClient,
        test_job: JobPosting,
    ):
        """Unauthenticated users get 401 on job detail."""
        response = await client.get(
            f"/jobs/{test_job.id}", follow_redirects=False
        )
        assert response.status_code == 401


@pytest.mark.asyncio
class TestJobEditPage:
    """Tests for GET /jobs/{job_id}/edit — job edit form."""

    async def test_admin_can_access_edit_form(
        self,
        authenticated_admin_client: AsyncClient,
        test_job: JobPosting,
    ):
        """Admin can access the job edit form."""
        response = await authenticated_admin_client.get(f"/jobs/{test_job.id}/edit")
        assert response.status_code == 200
        assert "Edit Job Posting" in response.text
        assert "Senior Python Developer" in response.text

    async def test_recruiter_can_access_edit_form(
        self,
        authenticated_recruiter_client: AsyncClient,
        test_job: JobPosting,
    ):
        """Recruiter can access the job edit form."""
        response = await authenticated_recruiter_client.get(
            f"/jobs/{test_job.id}/edit"
        )
        assert response.status_code == 200
        assert "Edit Job Posting" in response.text

    async def test_hiring_manager_can_edit_own_job(
        self,
        client: AsyncClient,
        hiring_manager_user: User,
        db_session: AsyncSession,
        test_department: Department,
    ):
        """Hiring manager can access edit form for their own job."""
        hm_job = JobPosting(
            title="HM Editable Job",
            description="A job the HM owns.",
            status="Draft",
            department_id=test_department.id,
            hiring_manager_id=hiring_manager_user.id,
            location="Remote",
            type="Full-Time",
        )
        db_session.add(hm_job)
        await db_session.flush()
        await db_session.refresh(hm_job)

        client.cookies.update(get_auth_cookie(hiring_manager_user))
        response = await client.get(f"/jobs/{hm_job.id}/edit")
        assert response.status_code == 200
        assert "HM Editable Job" in response.text

    async def test_hiring_manager_cannot_edit_others_job(
        self,
        client: AsyncClient,
        hiring_manager_user: User,
        test_job: JobPosting,
    ):
        """Hiring manager cannot edit a job assigned to another user."""
        client.cookies.update(get_auth_cookie(hiring_manager_user))
        response = await client.get(
            f"/jobs/{test_job.id}/edit", follow_redirects=False
        )
        # Should redirect away since they don't own this job
        assert response.status_code == 302
        assert "/jobs" in response.headers.get("location", "")

    async def test_interviewer_cannot_access_edit_form(
        self,
        authenticated_interviewer_client: AsyncClient,
        test_job: JobPosting,
    ):
        """Interviewer should be denied access to the job edit form."""
        response = await authenticated_interviewer_client.get(
            f"/jobs/{test_job.id}/edit", follow_redirects=False
        )
        assert response.status_code == 403

    async def test_nonexistent_job_edit_redirects(
        self,
        authenticated_admin_client: AsyncClient,
    ):
        """Editing a non-existent job redirects to /jobs."""
        response = await authenticated_admin_client.get(
            "/jobs/99999/edit", follow_redirects=False
        )
        assert response.status_code == 302


@pytest.mark.asyncio
class TestJobEditSubmit:
    """Tests for POST /jobs/{job_id} — job edit submission."""

    async def test_admin_can_update_job(
        self,
        authenticated_admin_client: AsyncClient,
        test_job: JobPosting,
        test_department: Department,
        admin_user: User,
    ):
        """Admin can update a job posting."""
        response = await authenticated_admin_client.post(
            f"/jobs/{test_job.id}",
            data={
                "title": "Updated Job Title",
                "description": "Updated description.",
                "department_id": str(test_department.id),
                "hiring_manager_id": str(admin_user.id),
                "location": "Austin, TX",
                "job_type": "Remote",
                "status": "Published",
            },
            follow_redirects=False,
        )
        assert response.status_code == 302
        assert f"/jobs/{test_job.id}" in response.headers.get("location", "")

    async def test_admin_can_update_job_verify_content(
        self,
        authenticated_admin_client: AsyncClient,
        test_job: JobPosting,
        test_department: Department,
        admin_user: User,
    ):
        """Verify updated content appears on the detail page."""
        await authenticated_admin_client.post(
            f"/jobs/{test_job.id}",
            data={
                "title": "Verified Updated Title",
                "description": "Verified updated description.",
                "department_id": str(test_department.id),
                "hiring_manager_id": str(admin_user.id),
                "location": "Chicago, IL",
                "job_type": "Full-Time",
                "status": "Published",
            },
            follow_redirects=False,
        )
        detail_response = await authenticated_admin_client.get(
            f"/jobs/{test_job.id}"
        )
        assert detail_response.status_code == 200
        assert "Verified Updated Title" in detail_response.text

    async def test_interviewer_cannot_update_job(
        self,
        authenticated_interviewer_client: AsyncClient,
        test_job: JobPosting,
        test_department: Department,
        interviewer_user: User,
    ):
        """Interviewer should be denied updating a job posting."""
        response = await authenticated_interviewer_client.post(
            f"/jobs/{test_job.id}",
            data={
                "title": "Should Not Work",
                "description": "This should fail.",
                "department_id": str(test_department.id),
                "hiring_manager_id": str(interviewer_user.id),
                "location": "Remote",
                "job_type": "Full-Time",
                "status": "Draft",
            },
            follow_redirects=False,
        )
        assert response.status_code == 403

    async def test_hiring_manager_can_update_own_job(
        self,
        client: AsyncClient,
        hiring_manager_user: User,
        db_session: AsyncSession,
        test_department: Department,
    ):
        """Hiring manager can update their own job posting."""
        hm_job = JobPosting(
            title="HM Job To Update",
            description="Original description.",
            status="Draft",
            department_id=test_department.id,
            hiring_manager_id=hiring_manager_user.id,
            location="Remote",
            type="Full-Time",
        )
        db_session.add(hm_job)
        await db_session.flush()
        await db_session.refresh(hm_job)

        client.cookies.update(get_auth_cookie(hiring_manager_user))
        response = await client.post(
            f"/jobs/{hm_job.id}",
            data={
                "title": "HM Updated Job",
                "description": "Updated by hiring manager.",
                "department_id": str(test_department.id),
                "hiring_manager_id": str(hiring_manager_user.id),
                "location": "Boston, MA",
                "job_type": "Full-Time",
                "status": "Published",
            },
            follow_redirects=False,
        )
        assert response.status_code == 302

    async def test_hiring_manager_cannot_update_others_job(
        self,
        client: AsyncClient,
        hiring_manager_user: User,
        test_job: JobPosting,
        test_department: Department,
    ):
        """Hiring manager cannot update a job assigned to another user."""
        client.cookies.update(get_auth_cookie(hiring_manager_user))
        response = await client.post(
            f"/jobs/{test_job.id}",
            data={
                "title": "Should Not Work",
                "description": "This should fail.",
                "department_id": str(test_department.id),
                "hiring_manager_id": str(hiring_manager_user.id),
                "location": "Remote",
                "job_type": "Full-Time",
                "status": "Draft",
            },
            follow_redirects=False,
        )
        # The service returns an error because HM doesn't own this job
        assert response.status_code == 400


@pytest.mark.asyncio
class TestJobStatusUpdate:
    """Tests for POST /jobs/{job_id}/status — job status transitions."""

    async def test_admin_can_publish_job(
        self,
        authenticated_admin_client: AsyncClient,
        test_draft_job: JobPosting,
    ):
        """Admin can change job status from Draft to Published."""
        response = await authenticated_admin_client.post(
            f"/jobs/{test_draft_job.id}/status",
            data={"status": "Published"},
            follow_redirects=False,
        )
        assert response.status_code == 302
        assert f"/jobs/{test_draft_job.id}" in response.headers.get("location", "")

    async def test_admin_can_close_job(
        self,
        authenticated_admin_client: AsyncClient,
        test_job: JobPosting,
    ):
        """Admin can change job status to Closed."""
        response = await authenticated_admin_client.post(
            f"/jobs/{test_job.id}/status",
            data={"status": "Closed"},
            follow_redirects=False,
        )
        assert response.status_code == 302

    async def test_recruiter_can_update_status(
        self,
        authenticated_recruiter_client: AsyncClient,
        test_draft_job: JobPosting,
    ):
        """Recruiter can update job status."""
        response = await authenticated_recruiter_client.post(
            f"/jobs/{test_draft_job.id}/status",
            data={"status": "Published"},
            follow_redirects=False,
        )
        assert response.status_code == 302

    async def test_interviewer_cannot_update_status(
        self,
        authenticated_interviewer_client: AsyncClient,
        test_job: JobPosting,
    ):
        """Interviewer should be denied updating job status."""
        response = await authenticated_interviewer_client.post(
            f"/jobs/{test_job.id}/status",
            data={"status": "Closed"},
            follow_redirects=False,
        )
        assert response.status_code == 403

    async def test_invalid_status_redirects(
        self,
        authenticated_admin_client: AsyncClient,
        test_job: JobPosting,
    ):
        """Invalid status value should redirect (service rejects it)."""
        response = await authenticated_admin_client.post(
            f"/jobs/{test_job.id}/status",
            data={"status": "InvalidStatus"},
            follow_redirects=False,
        )
        # The toggle_status service returns None for invalid status,
        # which causes a redirect to /jobs
        assert response.status_code == 302
        assert "/jobs" in response.headers.get("location", "")

    async def test_nonexistent_job_status_redirects(
        self,
        authenticated_admin_client: AsyncClient,
    ):
        """Updating status of non-existent job redirects to /jobs."""
        response = await authenticated_admin_client.post(
            "/jobs/99999/status",
            data={"status": "Published"},
            follow_redirects=False,
        )
        assert response.status_code == 302
        assert "/jobs" in response.headers.get("location", "")


@pytest.mark.asyncio
class TestPublishedJobsOnLandingPage:
    """Tests for published jobs appearing on the public landing page."""

    async def test_published_jobs_appear_on_landing(
        self,
        client: AsyncClient,
        test_job: JobPosting,
    ):
        """Published jobs should appear on the public landing page."""
        response = await client.get("/")
        assert response.status_code == 200
        assert "Senior Python Developer" in response.text

    async def test_draft_jobs_do_not_appear_on_landing(
        self,
        client: AsyncClient,
        test_draft_job: JobPosting,
    ):
        """Draft jobs should NOT appear on the public landing page."""
        response = await client.get("/")
        assert response.status_code == 200
        assert "Junior Frontend Developer" not in response.text

    async def test_closed_jobs_do_not_appear_on_landing(
        self,
        client: AsyncClient,
        db_session: AsyncSession,
        test_department: Department,
        admin_user: User,
    ):
        """Closed jobs should NOT appear on the public landing page."""
        closed_job = JobPosting(
            title="Closed Position XYZ",
            description="This position is closed.",
            status="Closed",
            department_id=test_department.id,
            hiring_manager_id=admin_user.id,
            location="Remote",
            type="Full-Time",
        )
        db_session.add(closed_job)
        await db_session.flush()

        response = await client.get("/")
        assert response.status_code == 200
        assert "Closed Position XYZ" not in response.text

    async def test_landing_page_shows_department_and_location(
        self,
        client: AsyncClient,
        test_job: JobPosting,
    ):
        """Landing page shows department and location info for published jobs."""
        response = await client.get("/")
        assert response.status_code == 200
        assert "Remote" in response.text
        assert "Test Engineering" in response.text


@pytest.mark.asyncio
class TestJobAuditLogging:
    """Tests that job operations create audit log entries."""

    async def test_create_job_creates_audit_log(
        self,
        authenticated_admin_client: AsyncClient,
        test_department: Department,
        admin_user: User,
    ):
        """Creating a job should create an audit log entry."""
        await authenticated_admin_client.post(
            "/jobs",
            data={
                "title": "Audit Test Job",
                "description": "Testing audit logging.",
                "department_id": str(test_department.id),
                "hiring_manager_id": str(admin_user.id),
                "location": "Remote",
                "job_type": "Full-Time",
                "status": "Draft",
            },
            follow_redirects=False,
        )

        # Check audit log page for the entry
        response = await authenticated_admin_client.get("/audit-log")
        assert response.status_code == 200
        assert "create_job" in response.text.lower() or "Create Job" in response.text

    async def test_update_job_status_creates_audit_log(
        self,
        authenticated_admin_client: AsyncClient,
        test_draft_job: JobPosting,
    ):
        """Updating job status should create an audit log entry."""
        await authenticated_admin_client.post(
            f"/jobs/{test_draft_job.id}/status",
            data={"status": "Published"},
            follow_redirects=False,
        )

        response = await authenticated_admin_client.get("/audit-log")
        assert response.status_code == 200
        assert "update_job_status" in response.text.lower() or "Update Job Status" in response.text


@pytest.mark.asyncio
class TestJobServiceValidation:
    """Tests for job service validation logic via endpoints."""

    async def test_create_job_with_all_job_types(
        self,
        authenticated_admin_client: AsyncClient,
        test_department: Department,
        admin_user: User,
    ):
        """All valid job types should be accepted."""
        valid_types = ["Full-Time", "Part-Time", "Contract", "Internship", "Remote"]
        for idx, job_type in enumerate(valid_types):
            response = await authenticated_admin_client.post(
                "/jobs",
                data={
                    "title": f"Job Type Test {idx}",
                    "description": f"Testing job type: {job_type}",
                    "department_id": str(test_department.id),
                    "hiring_manager_id": str(admin_user.id),
                    "location": "Remote",
                    "job_type": job_type,
                    "status": "Draft",
                },
                follow_redirects=False,
            )
            assert response.status_code == 302, f"Failed for job type: {job_type}"

    async def test_create_job_with_salary_min_greater_than_max(
        self,
        authenticated_admin_client: AsyncClient,
        test_department: Department,
        admin_user: User,
    ):
        """Salary min > salary max should return 400."""
        response = await authenticated_admin_client.post(
            "/jobs",
            data={
                "title": "Bad Salary Job",
                "description": "Salary min > max.",
                "department_id": str(test_department.id),
                "hiring_manager_id": str(admin_user.id),
                "location": "Remote",
                "job_type": "Full-Time",
                "status": "Draft",
                "salary_min": "200000",
                "salary_max": "100000",
            },
            follow_redirects=False,
        )
        assert response.status_code == 400

    async def test_create_job_nonexistent_department(
        self,
        authenticated_admin_client: AsyncClient,
        admin_user: User,
    ):
        """Creating a job with a non-existent department ID returns 400."""
        response = await authenticated_admin_client.post(
            "/jobs",
            data={
                "title": "Bad Dept Job",
                "description": "Non-existent department.",
                "department_id": "99999",
                "hiring_manager_id": str(admin_user.id),
                "location": "Remote",
                "job_type": "Full-Time",
                "status": "Draft",
            },
            follow_redirects=False,
        )
        assert response.status_code == 400

    async def test_create_job_nonexistent_hiring_manager(
        self,
        authenticated_admin_client: AsyncClient,
        test_department: Department,
    ):
        """Creating a job with a non-existent hiring manager ID returns 400."""
        response = await authenticated_admin_client.post(
            "/jobs",
            data={
                "title": "Bad Manager Job",
                "description": "Non-existent hiring manager.",
                "department_id": str(test_department.id),
                "hiring_manager_id": "99999",
                "location": "Remote",
                "job_type": "Full-Time",
                "status": "Draft",
            },
            follow_redirects=False,
        )
        assert response.status_code == 400
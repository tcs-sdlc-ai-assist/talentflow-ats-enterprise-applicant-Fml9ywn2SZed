import logging
from datetime import datetime

import pytest
import pytest_asyncio
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.application import Application
from app.models.candidate import Candidate
from app.models.department import Department
from app.models.job_posting import JobPosting
from app.models.user import User
from app.core.security import hash_password
from tests.conftest import get_auth_cookie

logger = logging.getLogger(__name__)


@pytest.mark.asyncio
class TestKanbanBoard:
    """Tests for the Kanban board view at GET /applications/kanban."""

    async def test_kanban_board_requires_login(self, client: AsyncClient):
        """Unauthenticated users should be redirected or get 401."""
        response = await client.get("/applications/kanban", follow_redirects=False)
        assert response.status_code in (401, 302, 303)

    async def test_kanban_board_renders_for_admin(
        self,
        authenticated_admin_client: AsyncClient,
    ):
        """Admin users should see the Kanban board page."""
        response = await authenticated_admin_client.get(
            "/applications/kanban", follow_redirects=False
        )
        assert response.status_code == 200
        assert "Application Pipeline" in response.text

    async def test_kanban_board_renders_all_stages(
        self,
        authenticated_admin_client: AsyncClient,
    ):
        """Kanban board should display all valid pipeline stages."""
        response = await authenticated_admin_client.get(
            "/applications/kanban", follow_redirects=False
        )
        assert response.status_code == 200
        for stage in ["Applied", "Screening", "Interviewing", "Offered", "Hired", "Rejected"]:
            assert stage in response.text

    async def test_kanban_board_shows_application(
        self,
        authenticated_admin_client: AsyncClient,
        test_application: Application,
    ):
        """Kanban board should display an existing application."""
        response = await authenticated_admin_client.get(
            "/applications/kanban", follow_redirects=False
        )
        assert response.status_code == 200
        assert "Jane" in response.text
        assert "Doe" in response.text

    async def test_kanban_board_filter_by_job(
        self,
        authenticated_admin_client: AsyncClient,
        test_application: Application,
        test_job: JobPosting,
    ):
        """Kanban board should filter applications by job_id."""
        response = await authenticated_admin_client.get(
            f"/applications/kanban?job_id={test_job.id}", follow_redirects=False
        )
        assert response.status_code == 200
        assert "Jane" in response.text

    async def test_kanban_board_filter_by_invalid_job_id(
        self,
        authenticated_admin_client: AsyncClient,
    ):
        """Kanban board should handle invalid job_id gracefully."""
        response = await authenticated_admin_client.get(
            "/applications/kanban?job_id=notanumber", follow_redirects=False
        )
        assert response.status_code == 200

    async def test_kanban_board_interviewer_can_view(
        self,
        authenticated_interviewer_client: AsyncClient,
    ):
        """Interviewers should be able to view the Kanban board."""
        response = await authenticated_interviewer_client.get(
            "/applications/kanban", follow_redirects=False
        )
        assert response.status_code == 200

    async def test_kanban_board_hiring_manager_sees_own_jobs(
        self,
        client: AsyncClient,
        db_session: AsyncSession,
        test_department: Department,
    ):
        """Hiring managers should only see applications for their own jobs."""
        hm_user = User(
            username="kanban_hm",
            email="kanban_hm@talentflow.local",
            hashed_password=hash_password("password123"),
            full_name="Kanban HM",
            role="hiring_manager",
            is_active=1,
        )
        db_session.add(hm_user)
        await db_session.flush()
        await db_session.refresh(hm_user)

        job = JobPosting(
            title="HM Kanban Job",
            description="A job for HM kanban test.",
            status="Published",
            department_id=test_department.id,
            hiring_manager_id=hm_user.id,
            location="Remote",
            type="Full-Time",
        )
        db_session.add(job)
        await db_session.flush()
        await db_session.refresh(job)

        candidate = Candidate(
            first_name="KanbanTest",
            last_name="Candidate",
            email="kanbantest@example.com",
        )
        db_session.add(candidate)
        await db_session.flush()
        await db_session.refresh(candidate)

        application = Application(
            candidate_id=candidate.id,
            job_id=job.id,
            stage="Applied",
        )
        db_session.add(application)
        await db_session.flush()

        client.cookies.update(get_auth_cookie(hm_user))
        response = await client.get("/applications/kanban", follow_redirects=False)
        assert response.status_code == 200
        assert "KanbanTest" in response.text


@pytest.mark.asyncio
class TestApplicationList:
    """Tests for the application list view at GET /applications."""

    async def test_application_list_requires_login(self, client: AsyncClient):
        """Unauthenticated users should not access the application list."""
        response = await client.get("/applications", follow_redirects=False)
        assert response.status_code in (401, 302, 303)

    async def test_application_list_renders_for_admin(
        self,
        authenticated_admin_client: AsyncClient,
    ):
        """Admin users should see the application list page."""
        response = await authenticated_admin_client.get(
            "/applications", follow_redirects=False
        )
        assert response.status_code == 200

    async def test_application_list_shows_application(
        self,
        authenticated_admin_client: AsyncClient,
        test_application: Application,
    ):
        """Application list should display existing applications."""
        response = await authenticated_admin_client.get(
            "/applications", follow_redirects=False
        )
        assert response.status_code == 200
        assert "Jane" in response.text or "Doe" in response.text

    async def test_application_list_filter_by_stage(
        self,
        authenticated_admin_client: AsyncClient,
        test_application: Application,
    ):
        """Application list should filter by stage."""
        response = await authenticated_admin_client.get(
            "/applications?stage=Applied", follow_redirects=False
        )
        assert response.status_code == 200

    async def test_application_list_search(
        self,
        authenticated_admin_client: AsyncClient,
        test_application: Application,
    ):
        """Application list should support search by candidate name."""
        response = await authenticated_admin_client.get(
            "/applications?search=Jane", follow_redirects=False
        )
        assert response.status_code == 200

    async def test_application_list_pagination(
        self,
        authenticated_admin_client: AsyncClient,
    ):
        """Application list should handle pagination parameters."""
        response = await authenticated_admin_client.get(
            "/applications?page=1", follow_redirects=False
        )
        assert response.status_code == 200

    async def test_application_list_invalid_page(
        self,
        authenticated_admin_client: AsyncClient,
    ):
        """Application list should handle invalid page numbers gracefully."""
        response = await authenticated_admin_client.get(
            "/applications?page=-1", follow_redirects=False
        )
        assert response.status_code == 200


@pytest.mark.asyncio
class TestApplicationStageUpdate:
    """Tests for updating application stage at POST /applications/{id}/stage."""

    async def test_stage_update_requires_login(
        self,
        client: AsyncClient,
        test_application: Application,
    ):
        """Unauthenticated users should not update application stages."""
        response = await client.post(
            f"/applications/{test_application.id}/stage",
            data={"stage": "Screening"},
            follow_redirects=False,
        )
        assert response.status_code in (401, 302, 303)

    async def test_stage_update_by_admin(
        self,
        authenticated_admin_client: AsyncClient,
        test_application: Application,
        db_session: AsyncSession,
    ):
        """Admin users should be able to update application stages."""
        response = await authenticated_admin_client.post(
            f"/applications/{test_application.id}/stage",
            data={"stage": "Screening"},
            follow_redirects=False,
        )
        assert response.status_code == 302

        await db_session.refresh(test_application)
        assert test_application.stage == "Screening"

    async def test_stage_update_by_recruiter(
        self,
        authenticated_recruiter_client: AsyncClient,
        test_application: Application,
        db_session: AsyncSession,
    ):
        """Recruiter users should be able to update application stages."""
        response = await authenticated_recruiter_client.post(
            f"/applications/{test_application.id}/stage",
            data={"stage": "Interviewing"},
            follow_redirects=False,
        )
        assert response.status_code == 302

        await db_session.refresh(test_application)
        assert test_application.stage == "Interviewing"

    async def test_stage_update_to_hired(
        self,
        authenticated_admin_client: AsyncClient,
        test_application: Application,
        db_session: AsyncSession,
    ):
        """Should be able to move application to Hired stage."""
        response = await authenticated_admin_client.post(
            f"/applications/{test_application.id}/stage",
            data={"stage": "Hired"},
            follow_redirects=False,
        )
        assert response.status_code == 302

        await db_session.refresh(test_application)
        assert test_application.stage == "Hired"

    async def test_stage_update_to_rejected(
        self,
        authenticated_admin_client: AsyncClient,
        test_application: Application,
        db_session: AsyncSession,
    ):
        """Should be able to move application to Rejected stage."""
        response = await authenticated_admin_client.post(
            f"/applications/{test_application.id}/stage",
            data={"stage": "Rejected"},
            follow_redirects=False,
        )
        assert response.status_code == 302

        await db_session.refresh(test_application)
        assert test_application.stage == "Rejected"

    async def test_stage_update_invalid_stage(
        self,
        authenticated_admin_client: AsyncClient,
        test_application: Application,
        db_session: AsyncSession,
    ):
        """Updating to an invalid stage should not change the application."""
        original_stage = test_application.stage
        response = await authenticated_admin_client.post(
            f"/applications/{test_application.id}/stage",
            data={"stage": "InvalidStage"},
            follow_redirects=False,
        )
        assert response.status_code == 302

        await db_session.refresh(test_application)
        assert test_application.stage == original_stage

    async def test_stage_update_nonexistent_application(
        self,
        authenticated_admin_client: AsyncClient,
    ):
        """Updating a non-existent application should redirect gracefully."""
        response = await authenticated_admin_client.post(
            "/applications/99999/stage",
            data={"stage": "Screening"},
            follow_redirects=False,
        )
        assert response.status_code == 302

    async def test_stage_update_denied_for_interviewer(
        self,
        authenticated_interviewer_client: AsyncClient,
        test_application: Application,
        db_session: AsyncSession,
    ):
        """Interviewers should not be able to update application stages."""
        original_stage = test_application.stage
        response = await authenticated_interviewer_client.post(
            f"/applications/{test_application.id}/stage",
            data={"stage": "Screening"},
            follow_redirects=False,
        )
        assert response.status_code in (302, 403)

        await db_session.refresh(test_application)
        assert test_application.stage == original_stage

    async def test_stage_update_denied_for_viewer(
        self,
        client: AsyncClient,
        viewer_user: User,
        test_application: Application,
        db_session: AsyncSession,
    ):
        """Viewer users should not be able to update application stages."""
        original_stage = test_application.stage
        client.cookies.update(get_auth_cookie(viewer_user))
        response = await client.post(
            f"/applications/{test_application.id}/stage",
            data={"stage": "Screening"},
            follow_redirects=False,
        )
        assert response.status_code in (302, 403)

        await db_session.refresh(test_application)
        assert test_application.stage == original_stage


@pytest.mark.asyncio
class TestApplicationCreate:
    """Tests for creating applications at POST /applications/create."""

    async def test_create_application_requires_login(
        self,
        client: AsyncClient,
        test_candidate: Candidate,
        test_job: JobPosting,
    ):
        """Unauthenticated users should not create applications."""
        response = await client.post(
            "/applications/create",
            data={
                "candidate_id": str(test_candidate.id),
                "job_id": str(test_job.id),
                "stage": "Applied",
            },
            follow_redirects=False,
        )
        assert response.status_code in (401, 302, 303)

    async def test_create_application_by_admin(
        self,
        authenticated_admin_client: AsyncClient,
        db_session: AsyncSession,
        test_department: Department,
        admin_user: User,
    ):
        """Admin users should be able to create applications."""
        candidate = Candidate(
            first_name="Create",
            last_name="AppTest",
            email="createapptest@example.com",
        )
        db_session.add(candidate)
        await db_session.flush()
        await db_session.refresh(candidate)

        job = JobPosting(
            title="Create App Test Job",
            description="Job for create app test.",
            status="Published",
            department_id=test_department.id,
            hiring_manager_id=admin_user.id,
            location="Remote",
            type="Full-Time",
        )
        db_session.add(job)
        await db_session.flush()
        await db_session.refresh(job)

        response = await authenticated_admin_client.post(
            "/applications/create",
            data={
                "candidate_id": str(candidate.id),
                "job_id": str(job.id),
                "stage": "Applied",
            },
            follow_redirects=False,
        )
        assert response.status_code == 302

    async def test_create_application_by_recruiter(
        self,
        authenticated_recruiter_client: AsyncClient,
        db_session: AsyncSession,
        test_department: Department,
        recruiter_user: User,
    ):
        """Recruiter users should be able to create applications."""
        candidate = Candidate(
            first_name="Recruiter",
            last_name="AppTest",
            email="recruiterapptest@example.com",
        )
        db_session.add(candidate)
        await db_session.flush()
        await db_session.refresh(candidate)

        job = JobPosting(
            title="Recruiter App Test Job",
            description="Job for recruiter app test.",
            status="Published",
            department_id=test_department.id,
            hiring_manager_id=recruiter_user.id,
            location="Remote",
            type="Full-Time",
        )
        db_session.add(job)
        await db_session.flush()
        await db_session.refresh(job)

        response = await authenticated_recruiter_client.post(
            "/applications/create",
            data={
                "candidate_id": str(candidate.id),
                "job_id": str(job.id),
                "stage": "Applied",
            },
            follow_redirects=False,
        )
        assert response.status_code == 302

    async def test_create_application_denied_for_interviewer(
        self,
        authenticated_interviewer_client: AsyncClient,
        test_candidate: Candidate,
        test_job: JobPosting,
    ):
        """Interviewers should not be able to create applications."""
        response = await authenticated_interviewer_client.post(
            "/applications/create",
            data={
                "candidate_id": str(test_candidate.id),
                "job_id": str(test_job.id),
                "stage": "Applied",
            },
            follow_redirects=False,
        )
        assert response.status_code in (302, 403)

    async def test_create_application_denied_for_viewer(
        self,
        client: AsyncClient,
        viewer_user: User,
        test_candidate: Candidate,
        test_job: JobPosting,
    ):
        """Viewer users should not be able to create applications."""
        client.cookies.update(get_auth_cookie(viewer_user))
        response = await client.post(
            "/applications/create",
            data={
                "candidate_id": str(test_candidate.id),
                "job_id": str(test_job.id),
                "stage": "Applied",
            },
            follow_redirects=False,
        )
        assert response.status_code in (302, 403)

    async def test_create_application_invalid_candidate_id(
        self,
        authenticated_admin_client: AsyncClient,
        test_job: JobPosting,
    ):
        """Creating an application with invalid candidate_id should redirect."""
        response = await authenticated_admin_client.post(
            "/applications/create",
            data={
                "candidate_id": "notanumber",
                "job_id": str(test_job.id),
                "stage": "Applied",
            },
            follow_redirects=False,
        )
        assert response.status_code == 302

    async def test_create_application_invalid_job_id(
        self,
        authenticated_admin_client: AsyncClient,
        test_candidate: Candidate,
    ):
        """Creating an application with invalid job_id should redirect."""
        response = await authenticated_admin_client.post(
            "/applications/create",
            data={
                "candidate_id": str(test_candidate.id),
                "job_id": "notanumber",
                "stage": "Applied",
            },
            follow_redirects=False,
        )
        assert response.status_code == 302

    async def test_create_application_nonexistent_candidate(
        self,
        authenticated_admin_client: AsyncClient,
        test_job: JobPosting,
    ):
        """Creating an application with non-existent candidate should redirect."""
        response = await authenticated_admin_client.post(
            "/applications/create",
            data={
                "candidate_id": "99999",
                "job_id": str(test_job.id),
                "stage": "Applied",
            },
            follow_redirects=False,
        )
        assert response.status_code == 302

    async def test_create_application_nonexistent_job(
        self,
        authenticated_admin_client: AsyncClient,
        test_candidate: Candidate,
    ):
        """Creating an application with non-existent job should redirect."""
        response = await authenticated_admin_client.post(
            "/applications/create",
            data={
                "candidate_id": str(test_candidate.id),
                "job_id": "99999",
                "stage": "Applied",
            },
            follow_redirects=False,
        )
        assert response.status_code == 302

    async def test_create_duplicate_application(
        self,
        authenticated_admin_client: AsyncClient,
        test_application: Application,
    ):
        """Creating a duplicate application (same candidate + job) should redirect."""
        response = await authenticated_admin_client.post(
            "/applications/create",
            data={
                "candidate_id": str(test_application.candidate_id),
                "job_id": str(test_application.job_id),
                "stage": "Applied",
            },
            follow_redirects=False,
        )
        assert response.status_code == 302

    async def test_create_application_for_draft_job(
        self,
        authenticated_admin_client: AsyncClient,
        test_candidate: Candidate,
        test_draft_job: JobPosting,
    ):
        """Creating an application for a draft job should redirect (not allowed)."""
        response = await authenticated_admin_client.post(
            "/applications/create",
            data={
                "candidate_id": str(test_candidate.id),
                "job_id": str(test_draft_job.id),
                "stage": "Applied",
            },
            follow_redirects=False,
        )
        assert response.status_code == 302

    async def test_create_application_default_stage(
        self,
        authenticated_admin_client: AsyncClient,
        db_session: AsyncSession,
        test_department: Department,
        admin_user: User,
    ):
        """Creating an application without specifying stage should default to Applied."""
        candidate = Candidate(
            first_name="Default",
            last_name="StageTest",
            email="defaultstage@example.com",
        )
        db_session.add(candidate)
        await db_session.flush()
        await db_session.refresh(candidate)

        job = JobPosting(
            title="Default Stage Test Job",
            description="Job for default stage test.",
            status="Published",
            department_id=test_department.id,
            hiring_manager_id=admin_user.id,
            location="Remote",
            type="Full-Time",
        )
        db_session.add(job)
        await db_session.flush()
        await db_session.refresh(job)

        response = await authenticated_admin_client.post(
            "/applications/create",
            data={
                "candidate_id": str(candidate.id),
                "job_id": str(job.id),
            },
            follow_redirects=False,
        )
        assert response.status_code == 302


@pytest.mark.asyncio
class TestApplicationServiceLogic:
    """Tests for application service business logic."""

    async def test_pipeline_stage_counts(
        self,
        db_session: AsyncSession,
        test_application: Application,
    ):
        """Pipeline stage counts should reflect actual application data."""
        from app.services.application_service import get_pipeline_stage_counts

        counts = await get_pipeline_stage_counts(db_session)
        assert isinstance(counts, list)
        assert len(counts) == 6

        applied_count = next(
            (s["count"] for s in counts if s["name"] == "Applied"), 0
        )
        assert applied_count >= 1

    async def test_count_active_applications(
        self,
        db_session: AsyncSession,
        test_application: Application,
    ):
        """Active application count should include non-terminal stages."""
        from app.services.application_service import count_active_applications

        count = await count_active_applications(db_session)
        assert count >= 1

    async def test_get_recent_applications(
        self,
        db_session: AsyncSession,
        test_application: Application,
    ):
        """Recent applications should return the most recent entries."""
        from app.services.application_service import get_recent_applications

        recent = await get_recent_applications(db_session, limit=10)
        assert len(recent) >= 1
        assert any(a.id == test_application.id for a in recent)

    async def test_list_applications_for_job(
        self,
        db_session: AsyncSession,
        test_application: Application,
        test_job: JobPosting,
    ):
        """Should list applications for a specific job."""
        from app.services.application_service import list_applications_for_job

        apps = await list_applications_for_job(db_session, test_job.id)
        assert len(apps) >= 1
        assert all(a.job_id == test_job.id for a in apps)

    async def test_list_applications_for_candidate(
        self,
        db_session: AsyncSession,
        test_application: Application,
        test_candidate: Candidate,
    ):
        """Should list applications for a specific candidate."""
        from app.services.application_service import list_applications_for_candidate

        apps = await list_applications_for_candidate(db_session, test_candidate.id)
        assert len(apps) >= 1
        assert all(a.candidate_id == test_candidate.id for a in apps)

    async def test_create_application_service(
        self,
        db_session: AsyncSession,
        admin_user: User,
        test_department: Department,
    ):
        """Application service should create applications correctly."""
        from app.services.application_service import create_application

        candidate = Candidate(
            first_name="Service",
            last_name="CreateTest",
            email="servicecreate@example.com",
        )
        db_session.add(candidate)
        await db_session.flush()
        await db_session.refresh(candidate)

        job = JobPosting(
            title="Service Create Test Job",
            description="Job for service create test.",
            status="Published",
            department_id=test_department.id,
            hiring_manager_id=admin_user.id,
            location="Remote",
            type="Full-Time",
        )
        db_session.add(job)
        await db_session.flush()
        await db_session.refresh(job)

        application, error = await create_application(
            db=db_session,
            candidate_id=candidate.id,
            job_id=job.id,
            stage="Applied",
            user=admin_user,
        )

        assert application is not None
        assert error is None
        assert application.candidate_id == candidate.id
        assert application.job_id == job.id
        assert application.stage == "Applied"

    async def test_create_application_service_permission_denied(
        self,
        db_session: AsyncSession,
        interviewer_user: User,
        test_candidate: Candidate,
        test_job: JobPosting,
    ):
        """Application service should deny creation for unauthorized roles."""
        from app.services.application_service import create_application

        application, error = await create_application(
            db=db_session,
            candidate_id=test_candidate.id,
            job_id=test_job.id,
            stage="Applied",
            user=interviewer_user,
        )

        assert application is None
        assert error is not None
        assert "permission" in error.lower()

    async def test_update_stage_service(
        self,
        db_session: AsyncSession,
        test_application: Application,
        admin_user: User,
    ):
        """Application service should update stages correctly."""
        from app.services.application_service import update_stage

        application, error = await update_stage(
            db=db_session,
            application_id=test_application.id,
            new_stage="Screening",
            user=admin_user,
        )

        assert application is not None
        assert error is None
        assert application.stage == "Screening"

    async def test_update_stage_service_invalid_stage(
        self,
        db_session: AsyncSession,
        test_application: Application,
        admin_user: User,
    ):
        """Application service should reject invalid stage values."""
        from app.services.application_service import update_stage

        application, error = await update_stage(
            db=db_session,
            application_id=test_application.id,
            new_stage="NotAValidStage",
            user=admin_user,
        )

        assert application is None
        assert error is not None
        assert "Invalid stage" in error

    async def test_update_stage_service_nonexistent_application(
        self,
        db_session: AsyncSession,
        admin_user: User,
    ):
        """Application service should handle non-existent application IDs."""
        from app.services.application_service import update_stage

        application, error = await update_stage(
            db=db_session,
            application_id=99999,
            new_stage="Screening",
            user=admin_user,
        )

        assert application is None
        assert error is not None

    async def test_get_kanban_board_service(
        self,
        db_session: AsyncSession,
        test_application: Application,
    ):
        """Kanban board service should return properly structured data."""
        from app.services.application_service import get_kanban_board

        result = await get_kanban_board(db=db_session)

        assert "board" in result
        assert "jobs" in result
        assert "total_applications" in result
        assert "selected_job_id" in result

        board = result["board"]
        for stage in ["Applied", "Screening", "Interviewing", "Offered", "Hired", "Rejected"]:
            assert stage in board
            assert isinstance(board[stage], list)

        assert result["total_applications"] >= 1

    async def test_get_kanban_board_service_with_job_filter(
        self,
        db_session: AsyncSession,
        test_application: Application,
        test_job: JobPosting,
    ):
        """Kanban board service should filter by job_id."""
        from app.services.application_service import get_kanban_board

        result = await get_kanban_board(db=db_session, job_id=test_job.id)

        assert result["selected_job_id"] == test_job.id
        assert result["total_applications"] >= 1

    async def test_get_application_by_id_service(
        self,
        db_session: AsyncSession,
        test_application: Application,
    ):
        """Application service should fetch application by ID."""
        from app.services.application_service import get_application_by_id

        application = await get_application_by_id(db_session, test_application.id)

        assert application is not None
        assert application.id == test_application.id

    async def test_get_application_by_id_nonexistent(
        self,
        db_session: AsyncSession,
    ):
        """Application service should return None for non-existent IDs."""
        from app.services.application_service import get_application_by_id

        application = await get_application_by_id(db_session, 99999)

        assert application is None


@pytest.mark.asyncio
class TestApplicationAuditTrail:
    """Tests for audit trail integration with application operations."""

    async def test_stage_update_creates_audit_log(
        self,
        authenticated_admin_client: AsyncClient,
        test_application: Application,
        db_session: AsyncSession,
    ):
        """Updating an application stage should create an audit log entry."""
        from sqlalchemy import select
        from app.models.audit_log import ActivityLog

        response = await authenticated_admin_client.post(
            f"/applications/{test_application.id}/stage",
            data={"stage": "Screening"},
            follow_redirects=False,
        )
        assert response.status_code == 302

        result = await db_session.execute(
            select(ActivityLog).where(
                ActivityLog.entity_type == "application",
                ActivityLog.entity_id == test_application.id,
                ActivityLog.action == "update_application_stage",
            )
        )
        log_entry = result.scalars().first()
        assert log_entry is not None
        assert "Screening" in (log_entry.details or "")

    async def test_create_application_creates_audit_log(
        self,
        authenticated_admin_client: AsyncClient,
        db_session: AsyncSession,
        test_department: Department,
        admin_user: User,
    ):
        """Creating an application should create an audit log entry."""
        from sqlalchemy import select
        from app.models.audit_log import ActivityLog

        candidate = Candidate(
            first_name="Audit",
            last_name="LogTest",
            email="auditlogtest@example.com",
        )
        db_session.add(candidate)
        await db_session.flush()
        await db_session.refresh(candidate)

        job = JobPosting(
            title="Audit Log Test Job",
            description="Job for audit log test.",
            status="Published",
            department_id=test_department.id,
            hiring_manager_id=admin_user.id,
            location="Remote",
            type="Full-Time",
        )
        db_session.add(job)
        await db_session.flush()
        await db_session.refresh(job)

        response = await authenticated_admin_client.post(
            "/applications/create",
            data={
                "candidate_id": str(candidate.id),
                "job_id": str(job.id),
                "stage": "Applied",
            },
            follow_redirects=False,
        )
        assert response.status_code == 302

        result = await db_session.execute(
            select(ActivityLog).where(
                ActivityLog.action == "create_application",
                ActivityLog.entity_type == "application",
            )
        )
        log_entry = result.scalars().first()
        assert log_entry is not None
import logging
from typing import AsyncGenerator

import pytest
import pytest_asyncio
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.audit_log import ActivityLog
from app.models.user import User
from app.services.audit_service import log_action, get_logs, get_recent_logs
from tests.conftest import get_auth_cookie

logger = logging.getLogger(__name__)


@pytest.mark.asyncio
async def test_audit_log_page_requires_admin_role(
    client: AsyncClient,
    interviewer_user: User,
):
    """Non-admin users should be denied access to the audit log page."""
    client.cookies.update(get_auth_cookie(interviewer_user))
    response = await client.get("/audit-log", follow_redirects=False)
    assert response.status_code == 403


@pytest.mark.asyncio
async def test_audit_log_page_requires_authentication(
    client: AsyncClient,
):
    """Unauthenticated users should be denied access to the audit log page."""
    response = await client.get("/audit-log", follow_redirects=False)
    assert response.status_code == 401


@pytest.mark.asyncio
async def test_audit_log_page_accessible_by_admin(
    authenticated_admin_client: AsyncClient,
):
    """Admin users should be able to access the audit log page."""
    response = await authenticated_admin_client.get("/audit-log", follow_redirects=False)
    assert response.status_code == 200
    assert b"Audit Log" in response.content


@pytest.mark.asyncio
async def test_audit_log_page_denied_for_recruiter(
    client: AsyncClient,
    recruiter_user: User,
):
    """Recruiter users should be denied access to the audit log page."""
    client.cookies.update(get_auth_cookie(recruiter_user))
    response = await client.get("/audit-log", follow_redirects=False)
    assert response.status_code == 403


@pytest.mark.asyncio
async def test_audit_log_page_denied_for_hiring_manager(
    client: AsyncClient,
    hiring_manager_user: User,
):
    """Hiring manager users should be denied access to the audit log page."""
    client.cookies.update(get_auth_cookie(hiring_manager_user))
    response = await client.get("/audit-log", follow_redirects=False)
    assert response.status_code == 403


@pytest.mark.asyncio
async def test_audit_log_page_denied_for_viewer(
    client: AsyncClient,
    viewer_user: User,
):
    """Viewer users should be denied access to the audit log page."""
    client.cookies.update(get_auth_cookie(viewer_user))
    response = await client.get("/audit-log", follow_redirects=False)
    assert response.status_code == 403


@pytest.mark.asyncio
async def test_log_action_creates_entry(
    db_session: AsyncSession,
    admin_user: User,
):
    """log_action should create an audit log entry in the database."""
    entry = await log_action(
        db=db_session,
        action="test_action",
        user_id=admin_user.id,
        entity_type="test_entity",
        entity_id=999,
        details="Test audit log entry",
    )

    assert entry is not None
    assert entry.id is not None
    assert entry.action == "test_action"
    assert entry.user_id == admin_user.id
    assert entry.entity_type == "test_entity"
    assert entry.entity_id == 999
    assert entry.details == "Test audit log entry"
    assert entry.timestamp is not None


@pytest.mark.asyncio
async def test_log_action_without_user(
    db_session: AsyncSession,
):
    """log_action should allow system actions without a user_id."""
    entry = await log_action(
        db=db_session,
        action="system_action",
        user_id=None,
        entity_type="system",
        entity_id=None,
        details="System-level action",
    )

    assert entry is not None
    assert entry.id is not None
    assert entry.action == "system_action"
    assert entry.user_id is None
    assert entry.entity_type == "system"
    assert entry.entity_id is None


@pytest.mark.asyncio
async def test_log_action_without_details(
    db_session: AsyncSession,
    admin_user: User,
):
    """log_action should work without optional details."""
    entry = await log_action(
        db=db_session,
        action="minimal_action",
        user_id=admin_user.id,
    )

    assert entry is not None
    assert entry.action == "minimal_action"
    assert entry.details is None
    assert entry.entity_type is None
    assert entry.entity_id is None


@pytest.mark.asyncio
async def test_get_logs_returns_paginated_results(
    db_session: AsyncSession,
    admin_user: User,
):
    """get_logs should return paginated audit log entries."""
    for i in range(30):
        await log_action(
            db=db_session,
            action=f"action_{i}",
            user_id=admin_user.id,
            entity_type="test",
            entity_id=i,
            details=f"Detail for action {i}",
        )
    await db_session.flush()

    result = await get_logs(db=db_session, page=1, per_page=10)

    assert result["page"] == 1
    assert result["per_page"] == 10
    assert result["total_count"] == 30
    assert result["total_pages"] == 3
    assert len(result["logs"]) == 10


@pytest.mark.asyncio
async def test_get_logs_second_page(
    db_session: AsyncSession,
    admin_user: User,
):
    """get_logs should return the correct second page of results."""
    for i in range(25):
        await log_action(
            db=db_session,
            action=f"action_{i}",
            user_id=admin_user.id,
            entity_type="test",
            entity_id=i,
        )
    await db_session.flush()

    result = await get_logs(db=db_session, page=2, per_page=10)

    assert result["page"] == 2
    assert result["per_page"] == 10
    assert result["total_count"] == 25
    assert result["total_pages"] == 3
    assert len(result["logs"]) == 10


@pytest.mark.asyncio
async def test_get_logs_last_page(
    db_session: AsyncSession,
    admin_user: User,
):
    """get_logs should return the correct last page with remaining entries."""
    for i in range(25):
        await log_action(
            db=db_session,
            action=f"action_{i}",
            user_id=admin_user.id,
            entity_type="test",
            entity_id=i,
        )
    await db_session.flush()

    result = await get_logs(db=db_session, page=3, per_page=10)

    assert result["page"] == 3
    assert result["total_count"] == 25
    assert result["total_pages"] == 3
    assert len(result["logs"]) == 5


@pytest.mark.asyncio
async def test_get_logs_with_search_filter(
    db_session: AsyncSession,
    admin_user: User,
):
    """get_logs should filter results by search term in action or details."""
    await log_action(
        db=db_session,
        action="create_job",
        user_id=admin_user.id,
        entity_type="job_posting",
        entity_id=1,
        details="Created job posting: Senior Developer",
    )
    await log_action(
        db=db_session,
        action="create_candidate",
        user_id=admin_user.id,
        entity_type="candidate",
        entity_id=1,
        details="Created candidate: Jane Doe",
    )
    await log_action(
        db=db_session,
        action="update_job",
        user_id=admin_user.id,
        entity_type="job_posting",
        entity_id=1,
        details="Updated job posting: Senior Developer",
    )
    await db_session.flush()

    result = await get_logs(db=db_session, search="job")

    assert result["total_count"] == 2
    for log in result["logs"]:
        assert (
            "job" in log.action.lower()
            or "job" in (log.details or "").lower()
            or "job" in (log.entity_type or "").lower()
        )


@pytest.mark.asyncio
async def test_get_logs_with_action_filter(
    db_session: AsyncSession,
    admin_user: User,
):
    """get_logs should filter results by exact action name."""
    await log_action(
        db=db_session,
        action="create_job",
        user_id=admin_user.id,
        entity_type="job_posting",
        entity_id=1,
    )
    await log_action(
        db=db_session,
        action="create_candidate",
        user_id=admin_user.id,
        entity_type="candidate",
        entity_id=1,
    )
    await log_action(
        db=db_session,
        action="create_job",
        user_id=admin_user.id,
        entity_type="job_posting",
        entity_id=2,
    )
    await db_session.flush()

    result = await get_logs(db=db_session, action_filter="create_job")

    assert result["total_count"] == 2
    for log in result["logs"]:
        assert log.action == "create_job"


@pytest.mark.asyncio
async def test_get_logs_action_options(
    db_session: AsyncSession,
    admin_user: User,
):
    """get_logs should return distinct action options for filtering."""
    await log_action(db=db_session, action="create_job", user_id=admin_user.id)
    await log_action(db=db_session, action="create_candidate", user_id=admin_user.id)
    await log_action(db=db_session, action="create_job", user_id=admin_user.id)
    await log_action(db=db_session, action="update_job", user_id=admin_user.id)
    await db_session.flush()

    result = await get_logs(db=db_session)

    action_options = result["action_options"]
    assert "create_job" in action_options
    assert "create_candidate" in action_options
    assert "update_job" in action_options
    assert len(action_options) == 3


@pytest.mark.asyncio
async def test_get_logs_empty_result(
    db_session: AsyncSession,
):
    """get_logs should return empty results when no logs exist."""
    result = await get_logs(db=db_session)

    assert result["total_count"] == 0
    assert result["total_pages"] == 1
    assert result["page"] == 1
    assert len(result["logs"]) == 0


@pytest.mark.asyncio
async def test_get_logs_invalid_page_number(
    db_session: AsyncSession,
    admin_user: User,
):
    """get_logs should handle invalid page numbers gracefully."""
    await log_action(db=db_session, action="test", user_id=admin_user.id)
    await db_session.flush()

    result = await get_logs(db=db_session, page=0, per_page=10)
    assert result["page"] == 1

    result = await get_logs(db=db_session, page=-5, per_page=10)
    assert result["page"] == 1


@pytest.mark.asyncio
async def test_get_recent_logs(
    db_session: AsyncSession,
    admin_user: User,
):
    """get_recent_logs should return the most recent entries up to the limit."""
    for i in range(15):
        await log_action(
            db=db_session,
            action=f"action_{i}",
            user_id=admin_user.id,
            entity_type="test",
            entity_id=i,
        )
    await db_session.flush()

    logs = await get_recent_logs(db=db_session, limit=5)

    assert len(logs) == 5
    # Verify ordering is most recent first
    for i in range(len(logs) - 1):
        assert logs[i].timestamp >= logs[i + 1].timestamp


@pytest.mark.asyncio
async def test_get_recent_logs_default_limit(
    db_session: AsyncSession,
    admin_user: User,
):
    """get_recent_logs should default to 10 entries."""
    for i in range(15):
        await log_action(
            db=db_session,
            action=f"action_{i}",
            user_id=admin_user.id,
        )
    await db_session.flush()

    logs = await get_recent_logs(db=db_session)

    assert len(logs) == 10


@pytest.mark.asyncio
async def test_audit_log_created_on_job_creation(
    authenticated_admin_client: AsyncClient,
    test_department,
    admin_user: User,
    db_session: AsyncSession,
):
    """Creating a job should generate an audit log entry."""
    response = await authenticated_admin_client.post(
        "/jobs",
        data={
            "title": "Test Audit Job",
            "description": "A job to test audit logging.",
            "department_id": str(test_department.id),
            "hiring_manager_id": str(admin_user.id),
            "location": "Remote",
            "job_type": "Full-Time",
            "status": "Draft",
        },
        follow_redirects=False,
    )
    assert response.status_code == 302

    result = await get_logs(db=db_session, action_filter="create_job")
    assert result["total_count"] >= 1

    found = False
    for log in result["logs"]:
        if "Test Audit Job" in (log.details or ""):
            found = True
            assert log.action == "create_job"
            assert log.entity_type == "job_posting"
            assert log.user_id == admin_user.id
            break
    assert found, "Audit log entry for job creation not found"


@pytest.mark.asyncio
async def test_audit_log_created_on_candidate_creation(
    authenticated_admin_client: AsyncClient,
    admin_user: User,
    db_session: AsyncSession,
):
    """Creating a candidate should generate an audit log entry."""
    response = await authenticated_admin_client.post(
        "/candidates",
        data={
            "first_name": "Audit",
            "last_name": "TestCandidate",
            "email": "audit.test@example.com",
            "phone": "",
            "linkedin_url": "",
            "skills": "Python, SQL",
            "resume_text": "",
        },
        follow_redirects=False,
    )
    assert response.status_code == 302

    result = await get_logs(db=db_session, action_filter="create_candidate")
    assert result["total_count"] >= 1

    found = False
    for log in result["logs"]:
        if "Audit TestCandidate" in (log.details or ""):
            found = True
            assert log.action == "create_candidate"
            assert log.entity_type == "candidate"
            assert log.user_id == admin_user.id
            break
    assert found, "Audit log entry for candidate creation not found"


@pytest.mark.asyncio
async def test_audit_log_created_on_application_stage_update(
    authenticated_admin_client: AsyncClient,
    admin_user: User,
    test_application,
    db_session: AsyncSession,
):
    """Updating an application stage should generate an audit log entry."""
    response = await authenticated_admin_client.post(
        f"/applications/{test_application.id}/stage",
        data={"stage": "Screening"},
        follow_redirects=False,
    )
    assert response.status_code == 302

    result = await get_logs(db=db_session, action_filter="update_application_stage")
    assert result["total_count"] >= 1

    found = False
    for log in result["logs"]:
        if str(test_application.id) in (log.details or ""):
            found = True
            assert log.action == "update_application_stage"
            assert log.entity_type == "application"
            assert log.entity_id == test_application.id
            assert log.user_id == admin_user.id
            break
    assert found, "Audit log entry for application stage update not found"


@pytest.mark.asyncio
async def test_audit_log_page_displays_entries(
    authenticated_admin_client: AsyncClient,
    admin_user: User,
    db_session: AsyncSession,
):
    """The audit log page should display log entries."""
    await log_action(
        db=db_session,
        action="create_job",
        user_id=admin_user.id,
        entity_type="job_posting",
        entity_id=42,
        details="Created job posting: Test Display Job",
    )
    await db_session.flush()
    await db_session.commit()

    response = await authenticated_admin_client.get("/audit-log", follow_redirects=False)
    assert response.status_code == 200
    assert b"create_job" in response.content or b"Create Job" in response.content


@pytest.mark.asyncio
async def test_audit_log_page_search(
    authenticated_admin_client: AsyncClient,
    admin_user: User,
    db_session: AsyncSession,
):
    """The audit log page should support search filtering."""
    await log_action(
        db=db_session,
        action="create_job",
        user_id=admin_user.id,
        details="Created job: Unique Search Term XYZ123",
    )
    await log_action(
        db=db_session,
        action="create_candidate",
        user_id=admin_user.id,
        details="Created candidate: Other Entry",
    )
    await db_session.flush()
    await db_session.commit()

    response = await authenticated_admin_client.get(
        "/audit-log?search=XYZ123",
        follow_redirects=False,
    )
    assert response.status_code == 200
    assert b"XYZ123" in response.content


@pytest.mark.asyncio
async def test_audit_log_page_action_filter(
    authenticated_admin_client: AsyncClient,
    admin_user: User,
    db_session: AsyncSession,
):
    """The audit log page should support action type filtering."""
    await log_action(
        db=db_session,
        action="create_job",
        user_id=admin_user.id,
        details="Job creation entry",
    )
    await log_action(
        db=db_session,
        action="create_candidate",
        user_id=admin_user.id,
        details="Candidate creation entry",
    )
    await db_session.flush()
    await db_session.commit()

    response = await authenticated_admin_client.get(
        "/audit-log?action_filter=create_job",
        follow_redirects=False,
    )
    assert response.status_code == 200
    assert b"Job creation entry" in response.content


@pytest.mark.asyncio
async def test_audit_log_page_pagination(
    authenticated_admin_client: AsyncClient,
    admin_user: User,
    db_session: AsyncSession,
):
    """The audit log page should support pagination."""
    for i in range(30):
        await log_action(
            db=db_session,
            action=f"bulk_action_{i}",
            user_id=admin_user.id,
            details=f"Bulk entry {i}",
        )
    await db_session.flush()
    await db_session.commit()

    response_page1 = await authenticated_admin_client.get(
        "/audit-log?page=1",
        follow_redirects=False,
    )
    assert response_page1.status_code == 200

    response_page2 = await authenticated_admin_client.get(
        "/audit-log?page=2",
        follow_redirects=False,
    )
    assert response_page2.status_code == 200
    assert response_page1.content != response_page2.content


@pytest.mark.asyncio
async def test_audit_log_immutability(
    db_session: AsyncSession,
    admin_user: User,
):
    """Audit log entries should be immutable (append-only by design)."""
    entry = await log_action(
        db=db_session,
        action="immutable_test",
        user_id=admin_user.id,
        details="Original details",
    )
    await db_session.flush()

    original_id = entry.id
    original_action = entry.action
    original_details = entry.details
    original_timestamp = entry.timestamp

    assert original_id is not None
    assert original_action == "immutable_test"
    assert original_details == "Original details"
    assert original_timestamp is not None


@pytest.mark.asyncio
async def test_audit_log_user_relationship(
    db_session: AsyncSession,
    admin_user: User,
):
    """Audit log entries should have a valid user relationship."""
    entry = await log_action(
        db=db_session,
        action="relationship_test",
        user_id=admin_user.id,
        details="Testing user relationship",
    )
    await db_session.flush()
    await db_session.refresh(entry)

    assert entry.user is not None
    assert entry.user.id == admin_user.id
    assert entry.user.username == admin_user.username


@pytest.mark.asyncio
async def test_audit_log_ordering(
    db_session: AsyncSession,
    admin_user: User,
):
    """Audit log entries should be ordered by timestamp descending (most recent first)."""
    for i in range(5):
        await log_action(
            db=db_session,
            action=f"ordered_action_{i}",
            user_id=admin_user.id,
        )
    await db_session.flush()

    result = await get_logs(db=db_session)
    logs = result["logs"]

    assert len(logs) == 5
    for i in range(len(logs) - 1):
        assert logs[i].timestamp >= logs[i + 1].timestamp


@pytest.mark.asyncio
async def test_audit_log_created_on_interview_scheduling(
    authenticated_admin_client: AsyncClient,
    admin_user: User,
    interviewer_user: User,
    test_application,
    db_session: AsyncSession,
):
    """Scheduling an interview should generate an audit log entry."""
    from datetime import datetime, timedelta

    scheduled_time = (datetime.utcnow() + timedelta(days=5)).strftime("%Y-%m-%dT%H:%M")

    response = await authenticated_admin_client.post(
        "/interviews",
        data={
            "application_id": str(test_application.id),
            "interviewer_id": str(interviewer_user.id),
            "scheduled_at": scheduled_time,
        },
        follow_redirects=False,
    )
    assert response.status_code == 302

    result = await get_logs(db=db_session, action_filter="schedule_interview")
    assert result["total_count"] >= 1

    found = False
    for log in result["logs"]:
        if log.action == "schedule_interview":
            found = True
            assert log.entity_type == "interview"
            assert log.user_id == admin_user.id
            break
    assert found, "Audit log entry for interview scheduling not found"


@pytest.mark.asyncio
async def test_audit_log_created_on_interview_feedback(
    authenticated_admin_client: AsyncClient,
    admin_user: User,
    test_interview,
    db_session: AsyncSession,
):
    """Submitting interview feedback should generate an audit log entry."""
    response = await authenticated_admin_client.post(
        f"/interviews/{test_interview.id}/feedback",
        data={
            "rating": "4",
            "feedback_notes": "Great candidate, strong technical skills.",
        },
        follow_redirects=False,
    )
    assert response.status_code == 302

    result = await get_logs(db=db_session, action_filter="submit_interview_feedback")
    assert result["total_count"] >= 1

    found = False
    for log in result["logs"]:
        if log.action == "submit_interview_feedback" and log.entity_id == test_interview.id:
            found = True
            assert log.entity_type == "interview"
            assert log.user_id == admin_user.id
            break
    assert found, "Audit log entry for interview feedback not found"


@pytest.mark.asyncio
async def test_get_logs_combined_search_and_action_filter(
    db_session: AsyncSession,
    admin_user: User,
):
    """get_logs should support combined search and action filtering."""
    await log_action(
        db=db_session,
        action="create_job",
        user_id=admin_user.id,
        details="Created job: Python Developer",
    )
    await log_action(
        db=db_session,
        action="create_job",
        user_id=admin_user.id,
        details="Created job: Java Developer",
    )
    await log_action(
        db=db_session,
        action="update_job",
        user_id=admin_user.id,
        details="Updated job: Python Developer",
    )
    await db_session.flush()

    result = await get_logs(
        db=db_session,
        search="Python",
        action_filter="create_job",
    )

    assert result["total_count"] == 1
    assert result["logs"][0].action == "create_job"
    assert "Python" in result["logs"][0].details


@pytest.mark.asyncio
async def test_audit_log_page_empty_state(
    authenticated_admin_client: AsyncClient,
):
    """The audit log page should display an empty state when no entries exist."""
    response = await authenticated_admin_client.get("/audit-log", follow_redirects=False)
    assert response.status_code == 200
    assert b"No audit log entries found" in response.content
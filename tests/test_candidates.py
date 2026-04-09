import logging
from typing import AsyncGenerator

import pytest
import pytest_asyncio
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.candidate import Candidate
from app.models.skill import Skill
from app.models.user import User
from app.models.department import Department
from app.models.job_posting import JobPosting
from app.models.application import Application
from tests.conftest import get_auth_cookie

logger = logging.getLogger(__name__)


@pytest.mark.asyncio
class TestCandidateListPage:
    """Tests for GET /candidates — candidate listing page."""

    async def test_unauthenticated_user_redirected(self, client: AsyncClient):
        """Unauthenticated users should get 401 when accessing candidates."""
        response = await client.get("/candidates", follow_redirects=False)
        assert response.status_code == 401

    async def test_authenticated_user_can_view_candidates(
        self,
        client: AsyncClient,
        admin_user: User,
    ):
        """Any authenticated user can view the candidates list."""
        client.cookies.update(get_auth_cookie(admin_user))
        response = await client.get("/candidates")
        assert response.status_code == 200
        assert "Candidates" in response.text

    async def test_viewer_can_view_candidates(
        self,
        client: AsyncClient,
        viewer_user: User,
    ):
        """Viewer role can access the candidates list (read-only)."""
        client.cookies.update(get_auth_cookie(viewer_user))
        response = await client.get("/candidates")
        assert response.status_code == 200
        assert "Candidates" in response.text

    async def test_interviewer_can_view_candidates(
        self,
        client: AsyncClient,
        interviewer_user: User,
    ):
        """Interviewer role can access the candidates list."""
        client.cookies.update(get_auth_cookie(interviewer_user))
        response = await client.get("/candidates")
        assert response.status_code == 200

    async def test_candidates_displayed_in_list(
        self,
        client: AsyncClient,
        admin_user: User,
        test_candidate: Candidate,
    ):
        """Candidates should appear in the list page."""
        client.cookies.update(get_auth_cookie(admin_user))
        response = await client.get("/candidates")
        assert response.status_code == 200
        assert test_candidate.first_name in response.text
        assert test_candidate.last_name in response.text
        assert test_candidate.email in response.text

    async def test_candidate_search_by_name(
        self,
        client: AsyncClient,
        admin_user: User,
        test_candidate: Candidate,
    ):
        """Search should filter candidates by name."""
        client.cookies.update(get_auth_cookie(admin_user))
        response = await client.get(
            "/candidates", params={"search": test_candidate.first_name}
        )
        assert response.status_code == 200
        assert test_candidate.first_name in response.text

    async def test_candidate_search_by_email(
        self,
        client: AsyncClient,
        admin_user: User,
        test_candidate: Candidate,
    ):
        """Search should filter candidates by email."""
        client.cookies.update(get_auth_cookie(admin_user))
        response = await client.get(
            "/candidates", params={"search": "jane.doe"}
        )
        assert response.status_code == 200
        assert test_candidate.email in response.text

    async def test_candidate_search_no_results(
        self,
        client: AsyncClient,
        admin_user: User,
    ):
        """Search with no matching results should show empty state."""
        client.cookies.update(get_auth_cookie(admin_user))
        response = await client.get(
            "/candidates", params={"search": "nonexistentcandidate12345"}
        )
        assert response.status_code == 200
        assert "No candidates found" in response.text

    async def test_candidate_search_by_skill(
        self,
        client: AsyncClient,
        admin_user: User,
        test_candidate_with_skills: Candidate,
    ):
        """Search should filter candidates by skill name."""
        client.cookies.update(get_auth_cookie(admin_user))
        response = await client.get(
            "/candidates", params={"search": "Python"}
        )
        assert response.status_code == 200
        assert test_candidate_with_skills.first_name in response.text

    async def test_candidate_list_pagination(
        self,
        client: AsyncClient,
        admin_user: User,
    ):
        """Pagination parameter should be accepted."""
        client.cookies.update(get_auth_cookie(admin_user))
        response = await client.get("/candidates", params={"page": 1})
        assert response.status_code == 200

    async def test_candidate_list_invalid_page(
        self,
        client: AsyncClient,
        admin_user: User,
    ):
        """Invalid page number should default gracefully."""
        client.cookies.update(get_auth_cookie(admin_user))
        response = await client.get("/candidates", params={"page": -1})
        assert response.status_code == 200


@pytest.mark.asyncio
class TestCandidateCreatePage:
    """Tests for GET /candidates/create — candidate creation form."""

    async def test_unauthenticated_user_cannot_access_create_form(
        self, client: AsyncClient
    ):
        """Unauthenticated users should not access the create form."""
        response = await client.get("/candidates/create", follow_redirects=False)
        assert response.status_code == 401

    async def test_admin_can_access_create_form(
        self,
        client: AsyncClient,
        admin_user: User,
    ):
        """Admin users can access the candidate creation form."""
        client.cookies.update(get_auth_cookie(admin_user))
        response = await client.get("/candidates/create")
        assert response.status_code == 200
        assert "New Candidate" in response.text or "Add New Candidate" in response.text

    async def test_recruiter_can_access_create_form(
        self,
        client: AsyncClient,
        recruiter_user: User,
    ):
        """Recruiter users can access the candidate creation form."""
        client.cookies.update(get_auth_cookie(recruiter_user))
        response = await client.get("/candidates/create")
        assert response.status_code == 200

    async def test_hiring_manager_can_access_create_form(
        self,
        client: AsyncClient,
        hiring_manager_user: User,
    ):
        """Hiring manager users can access the candidate creation form."""
        client.cookies.update(get_auth_cookie(hiring_manager_user))
        response = await client.get("/candidates/create")
        assert response.status_code == 200

    async def test_interviewer_cannot_access_create_form(
        self,
        client: AsyncClient,
        interviewer_user: User,
    ):
        """Interviewer users should be denied access to the create form."""
        client.cookies.update(get_auth_cookie(interviewer_user))
        response = await client.get("/candidates/create", follow_redirects=False)
        assert response.status_code == 403

    async def test_viewer_cannot_access_create_form(
        self,
        client: AsyncClient,
        viewer_user: User,
    ):
        """Viewer users should be denied access to the create form."""
        client.cookies.update(get_auth_cookie(viewer_user))
        response = await client.get("/candidates/create", follow_redirects=False)
        assert response.status_code == 403


@pytest.mark.asyncio
class TestCandidateCreateSubmit:
    """Tests for POST /candidates — candidate creation submission."""

    async def test_admin_can_create_candidate(
        self,
        client: AsyncClient,
        admin_user: User,
    ):
        """Admin can create a new candidate."""
        client.cookies.update(get_auth_cookie(admin_user))
        response = await client.post(
            "/candidates",
            data={
                "first_name": "Alice",
                "last_name": "Johnson",
                "email": "alice.johnson@example.com",
                "phone": "+1-555-000-1111",
                "linkedin_url": "https://linkedin.com/in/alicejohnson",
                "skills": "Python, React, Docker",
                "resume_text": "Experienced full-stack developer.",
            },
            follow_redirects=False,
        )
        assert response.status_code == 302
        assert "/candidates/" in response.headers.get("location", "")

    async def test_recruiter_can_create_candidate(
        self,
        client: AsyncClient,
        recruiter_user: User,
    ):
        """Recruiter can create a new candidate."""
        client.cookies.update(get_auth_cookie(recruiter_user))
        response = await client.post(
            "/candidates",
            data={
                "first_name": "Bob",
                "last_name": "Williams",
                "email": "bob.williams@example.com",
                "phone": "",
                "linkedin_url": "",
                "skills": "",
                "resume_text": "",
            },
            follow_redirects=False,
        )
        assert response.status_code == 302
        assert "/candidates/" in response.headers.get("location", "")

    async def test_hiring_manager_can_create_candidate(
        self,
        client: AsyncClient,
        hiring_manager_user: User,
    ):
        """Hiring manager can create a new candidate."""
        client.cookies.update(get_auth_cookie(hiring_manager_user))
        response = await client.post(
            "/candidates",
            data={
                "first_name": "Carol",
                "last_name": "Davis",
                "email": "carol.davis@example.com",
                "phone": "",
                "linkedin_url": "",
                "skills": "Java, Spring",
                "resume_text": "",
            },
            follow_redirects=False,
        )
        assert response.status_code == 302

    async def test_interviewer_cannot_create_candidate(
        self,
        client: AsyncClient,
        interviewer_user: User,
    ):
        """Interviewer should be denied creating candidates."""
        client.cookies.update(get_auth_cookie(interviewer_user))
        response = await client.post(
            "/candidates",
            data={
                "first_name": "Denied",
                "last_name": "User",
                "email": "denied@example.com",
                "phone": "",
                "linkedin_url": "",
                "skills": "",
                "resume_text": "",
            },
            follow_redirects=False,
        )
        assert response.status_code == 403

    async def test_viewer_cannot_create_candidate(
        self,
        client: AsyncClient,
        viewer_user: User,
    ):
        """Viewer should be denied creating candidates."""
        client.cookies.update(get_auth_cookie(viewer_user))
        response = await client.post(
            "/candidates",
            data={
                "first_name": "Denied",
                "last_name": "Viewer",
                "email": "denied.viewer@example.com",
                "phone": "",
                "linkedin_url": "",
                "skills": "",
                "resume_text": "",
            },
            follow_redirects=False,
        )
        assert response.status_code == 403

    async def test_create_candidate_duplicate_email(
        self,
        client: AsyncClient,
        admin_user: User,
        test_candidate: Candidate,
    ):
        """Creating a candidate with a duplicate email should fail."""
        client.cookies.update(get_auth_cookie(admin_user))
        response = await client.post(
            "/candidates",
            data={
                "first_name": "Duplicate",
                "last_name": "Email",
                "email": test_candidate.email,
                "phone": "",
                "linkedin_url": "",
                "skills": "",
                "resume_text": "",
            },
            follow_redirects=False,
        )
        assert response.status_code == 400
        assert "already exists" in response.text

    async def test_create_candidate_with_skills(
        self,
        client: AsyncClient,
        admin_user: User,
    ):
        """Creating a candidate with skills should associate skill tags."""
        client.cookies.update(get_auth_cookie(admin_user))
        response = await client.post(
            "/candidates",
            data={
                "first_name": "Skilled",
                "last_name": "Developer",
                "email": "skilled.dev@example.com",
                "phone": "",
                "linkedin_url": "",
                "skills": "Python, FastAPI, SQL",
                "resume_text": "Expert in Python ecosystem.",
            },
            follow_redirects=False,
        )
        assert response.status_code == 302

        # Follow redirect to detail page and verify skills
        location = response.headers.get("location", "")
        assert "/candidates/" in location
        detail_response = await client.get(location)
        assert detail_response.status_code == 200
        assert "Python" in detail_response.text
        assert "FastAPI" in detail_response.text
        assert "SQL" in detail_response.text

    async def test_create_candidate_invalid_email(
        self,
        client: AsyncClient,
        admin_user: User,
    ):
        """Creating a candidate with an invalid email should fail."""
        client.cookies.update(get_auth_cookie(admin_user))
        response = await client.post(
            "/candidates",
            data={
                "first_name": "Invalid",
                "last_name": "Email",
                "email": "not-an-email",
                "phone": "",
                "linkedin_url": "",
                "skills": "",
                "resume_text": "",
            },
            follow_redirects=False,
        )
        assert response.status_code == 400

    async def test_create_candidate_minimal_fields(
        self,
        client: AsyncClient,
        admin_user: User,
    ):
        """Creating a candidate with only required fields should succeed."""
        client.cookies.update(get_auth_cookie(admin_user))
        response = await client.post(
            "/candidates",
            data={
                "first_name": "Minimal",
                "last_name": "Fields",
                "email": "minimal.fields@example.com",
                "phone": "",
                "linkedin_url": "",
                "skills": "",
                "resume_text": "",
            },
            follow_redirects=False,
        )
        assert response.status_code == 302


@pytest.mark.asyncio
class TestCandidateDetailPage:
    """Tests for GET /candidates/{candidate_id} — candidate detail view."""

    async def test_unauthenticated_user_cannot_view_detail(
        self,
        client: AsyncClient,
        test_candidate: Candidate,
    ):
        """Unauthenticated users should not access candidate detail."""
        response = await client.get(
            f"/candidates/{test_candidate.id}", follow_redirects=False
        )
        assert response.status_code == 401

    async def test_admin_can_view_candidate_detail(
        self,
        client: AsyncClient,
        admin_user: User,
        test_candidate: Candidate,
    ):
        """Admin can view candidate detail page."""
        client.cookies.update(get_auth_cookie(admin_user))
        response = await client.get(f"/candidates/{test_candidate.id}")
        assert response.status_code == 200
        assert test_candidate.first_name in response.text
        assert test_candidate.last_name in response.text
        assert test_candidate.email in response.text

    async def test_viewer_can_view_candidate_detail(
        self,
        client: AsyncClient,
        viewer_user: User,
        test_candidate: Candidate,
    ):
        """Viewer can view candidate detail page (read-only)."""
        client.cookies.update(get_auth_cookie(viewer_user))
        response = await client.get(f"/candidates/{test_candidate.id}")
        assert response.status_code == 200
        assert test_candidate.first_name in response.text

    async def test_interviewer_can_view_candidate_detail(
        self,
        client: AsyncClient,
        interviewer_user: User,
        test_candidate: Candidate,
    ):
        """Interviewer can view candidate detail page."""
        client.cookies.update(get_auth_cookie(interviewer_user))
        response = await client.get(f"/candidates/{test_candidate.id}")
        assert response.status_code == 200

    async def test_candidate_detail_shows_contact_info(
        self,
        client: AsyncClient,
        admin_user: User,
        test_candidate: Candidate,
    ):
        """Candidate detail should display contact information."""
        client.cookies.update(get_auth_cookie(admin_user))
        response = await client.get(f"/candidates/{test_candidate.id}")
        assert response.status_code == 200
        assert test_candidate.email in response.text
        if test_candidate.phone:
            assert test_candidate.phone in response.text

    async def test_candidate_detail_shows_skills(
        self,
        client: AsyncClient,
        admin_user: User,
        test_candidate_with_skills: Candidate,
    ):
        """Candidate detail should display associated skills."""
        client.cookies.update(get_auth_cookie(admin_user))
        response = await client.get(
            f"/candidates/{test_candidate_with_skills.id}"
        )
        assert response.status_code == 200
        assert "Python" in response.text

    async def test_candidate_detail_shows_resume(
        self,
        client: AsyncClient,
        admin_user: User,
        test_candidate: Candidate,
    ):
        """Candidate detail should display resume text."""
        client.cookies.update(get_auth_cookie(admin_user))
        response = await client.get(f"/candidates/{test_candidate.id}")
        assert response.status_code == 200
        if test_candidate.resume_text:
            assert "Resume" in response.text or "resume" in response.text

    async def test_candidate_detail_shows_applications(
        self,
        client: AsyncClient,
        admin_user: User,
        test_candidate: Candidate,
        test_application: Application,
    ):
        """Candidate detail should display associated applications."""
        client.cookies.update(get_auth_cookie(admin_user))
        response = await client.get(f"/candidates/{test_candidate.id}")
        assert response.status_code == 200
        assert "Applications" in response.text

    async def test_candidate_detail_nonexistent_id(
        self,
        client: AsyncClient,
        admin_user: User,
    ):
        """Accessing a non-existent candidate should return 404."""
        client.cookies.update(get_auth_cookie(admin_user))
        response = await client.get("/candidates/99999")
        assert response.status_code == 404

    async def test_candidate_detail_edit_button_visible_for_admin(
        self,
        client: AsyncClient,
        admin_user: User,
        test_candidate: Candidate,
    ):
        """Admin should see the edit button on candidate detail."""
        client.cookies.update(get_auth_cookie(admin_user))
        response = await client.get(f"/candidates/{test_candidate.id}")
        assert response.status_code == 200
        assert "Edit Candidate" in response.text

    async def test_candidate_detail_edit_button_hidden_for_viewer(
        self,
        client: AsyncClient,
        viewer_user: User,
        test_candidate: Candidate,
    ):
        """Viewer should NOT see the edit button on candidate detail."""
        client.cookies.update(get_auth_cookie(viewer_user))
        response = await client.get(f"/candidates/{test_candidate.id}")
        assert response.status_code == 200
        assert "Edit Candidate" not in response.text


@pytest.mark.asyncio
class TestCandidateEditPage:
    """Tests for GET /candidates/{candidate_id}/edit — candidate edit form."""

    async def test_unauthenticated_user_cannot_access_edit_form(
        self,
        client: AsyncClient,
        test_candidate: Candidate,
    ):
        """Unauthenticated users should not access the edit form."""
        response = await client.get(
            f"/candidates/{test_candidate.id}/edit", follow_redirects=False
        )
        assert response.status_code == 401

    async def test_admin_can_access_edit_form(
        self,
        client: AsyncClient,
        admin_user: User,
        test_candidate: Candidate,
    ):
        """Admin can access the candidate edit form."""
        client.cookies.update(get_auth_cookie(admin_user))
        response = await client.get(f"/candidates/{test_candidate.id}/edit")
        assert response.status_code == 200
        assert "Edit Candidate" in response.text
        assert test_candidate.first_name in response.text

    async def test_recruiter_can_access_edit_form(
        self,
        client: AsyncClient,
        recruiter_user: User,
        test_candidate: Candidate,
    ):
        """Recruiter can access the candidate edit form."""
        client.cookies.update(get_auth_cookie(recruiter_user))
        response = await client.get(f"/candidates/{test_candidate.id}/edit")
        assert response.status_code == 200

    async def test_interviewer_cannot_access_edit_form(
        self,
        client: AsyncClient,
        interviewer_user: User,
        test_candidate: Candidate,
    ):
        """Interviewer should be denied access to the edit form."""
        client.cookies.update(get_auth_cookie(interviewer_user))
        response = await client.get(
            f"/candidates/{test_candidate.id}/edit", follow_redirects=False
        )
        assert response.status_code == 403

    async def test_viewer_cannot_access_edit_form(
        self,
        client: AsyncClient,
        viewer_user: User,
        test_candidate: Candidate,
    ):
        """Viewer should be denied access to the edit form."""
        client.cookies.update(get_auth_cookie(viewer_user))
        response = await client.get(
            f"/candidates/{test_candidate.id}/edit", follow_redirects=False
        )
        assert response.status_code == 403

    async def test_edit_form_nonexistent_candidate(
        self,
        client: AsyncClient,
        admin_user: User,
    ):
        """Editing a non-existent candidate should redirect."""
        client.cookies.update(get_auth_cookie(admin_user))
        response = await client.get(
            "/candidates/99999/edit", follow_redirects=False
        )
        assert response.status_code == 302
        assert "/candidates" in response.headers.get("location", "")


@pytest.mark.asyncio
class TestCandidateEditSubmit:
    """Tests for POST /candidates/{candidate_id} — candidate edit submission."""

    async def test_admin_can_edit_candidate(
        self,
        client: AsyncClient,
        admin_user: User,
        test_candidate: Candidate,
    ):
        """Admin can update a candidate's information."""
        client.cookies.update(get_auth_cookie(admin_user))
        response = await client.post(
            f"/candidates/{test_candidate.id}",
            data={
                "first_name": "Jane Updated",
                "last_name": "Doe Updated",
                "email": test_candidate.email,
                "phone": "+1-555-999-8888",
                "linkedin_url": "https://linkedin.com/in/janedoeupdated",
                "skills": "Python, Go, Rust",
                "resume_text": "Updated resume text with more experience.",
            },
            follow_redirects=False,
        )
        assert response.status_code == 302
        assert f"/candidates/{test_candidate.id}" in response.headers.get(
            "location", ""
        )

    async def test_recruiter_can_edit_candidate(
        self,
        client: AsyncClient,
        recruiter_user: User,
        test_candidate: Candidate,
    ):
        """Recruiter can update a candidate's information."""
        client.cookies.update(get_auth_cookie(recruiter_user))
        response = await client.post(
            f"/candidates/{test_candidate.id}",
            data={
                "first_name": test_candidate.first_name,
                "last_name": test_candidate.last_name,
                "email": test_candidate.email,
                "phone": "+1-555-111-2222",
                "linkedin_url": "",
                "skills": "",
                "resume_text": "",
            },
            follow_redirects=False,
        )
        assert response.status_code == 302

    async def test_interviewer_cannot_edit_candidate(
        self,
        client: AsyncClient,
        interviewer_user: User,
        test_candidate: Candidate,
    ):
        """Interviewer should be denied editing candidates."""
        client.cookies.update(get_auth_cookie(interviewer_user))
        response = await client.post(
            f"/candidates/{test_candidate.id}",
            data={
                "first_name": "Denied",
                "last_name": "Edit",
                "email": test_candidate.email,
                "phone": "",
                "linkedin_url": "",
                "skills": "",
                "resume_text": "",
            },
            follow_redirects=False,
        )
        assert response.status_code == 403

    async def test_viewer_cannot_edit_candidate(
        self,
        client: AsyncClient,
        viewer_user: User,
        test_candidate: Candidate,
    ):
        """Viewer should be denied editing candidates."""
        client.cookies.update(get_auth_cookie(viewer_user))
        response = await client.post(
            f"/candidates/{test_candidate.id}",
            data={
                "first_name": "Denied",
                "last_name": "Edit",
                "email": test_candidate.email,
                "phone": "",
                "linkedin_url": "",
                "skills": "",
                "resume_text": "",
            },
            follow_redirects=False,
        )
        assert response.status_code == 403

    async def test_edit_candidate_change_email(
        self,
        client: AsyncClient,
        admin_user: User,
        test_candidate: Candidate,
    ):
        """Admin can change a candidate's email to a new unique email."""
        client.cookies.update(get_auth_cookie(admin_user))
        response = await client.post(
            f"/candidates/{test_candidate.id}",
            data={
                "first_name": test_candidate.first_name,
                "last_name": test_candidate.last_name,
                "email": "newemail@example.com",
                "phone": "",
                "linkedin_url": "",
                "skills": "",
                "resume_text": "",
            },
            follow_redirects=False,
        )
        assert response.status_code == 302

    async def test_edit_candidate_duplicate_email(
        self,
        client: AsyncClient,
        admin_user: User,
        test_candidate: Candidate,
        test_candidate_with_skills: Candidate,
    ):
        """Changing email to an existing candidate's email should fail."""
        client.cookies.update(get_auth_cookie(admin_user))
        response = await client.post(
            f"/candidates/{test_candidate.id}",
            data={
                "first_name": test_candidate.first_name,
                "last_name": test_candidate.last_name,
                "email": test_candidate_with_skills.email,
                "phone": "",
                "linkedin_url": "",
                "skills": "",
                "resume_text": "",
            },
            follow_redirects=False,
        )
        assert response.status_code == 400
        assert "already exists" in response.text

    async def test_edit_nonexistent_candidate(
        self,
        client: AsyncClient,
        admin_user: User,
    ):
        """Editing a non-existent candidate should redirect."""
        client.cookies.update(get_auth_cookie(admin_user))
        response = await client.post(
            "/candidates/99999",
            data={
                "first_name": "Ghost",
                "last_name": "Candidate",
                "email": "ghost@example.com",
                "phone": "",
                "linkedin_url": "",
                "skills": "",
                "resume_text": "",
            },
            follow_redirects=False,
        )
        assert response.status_code == 302
        assert "/candidates" in response.headers.get("location", "")

    async def test_edit_candidate_update_skills(
        self,
        client: AsyncClient,
        admin_user: User,
        test_candidate_with_skills: Candidate,
    ):
        """Editing a candidate should update their skill tags."""
        client.cookies.update(get_auth_cookie(admin_user))
        response = await client.post(
            f"/candidates/{test_candidate_with_skills.id}",
            data={
                "first_name": test_candidate_with_skills.first_name,
                "last_name": test_candidate_with_skills.last_name,
                "email": test_candidate_with_skills.email,
                "phone": "",
                "linkedin_url": "",
                "skills": "Go, Kubernetes, Terraform",
                "resume_text": "",
            },
            follow_redirects=False,
        )
        assert response.status_code == 302

        # Verify updated skills on detail page
        location = response.headers.get("location", "")
        detail_response = await client.get(location)
        assert detail_response.status_code == 200
        assert "Go" in detail_response.text
        assert "Kubernetes" in detail_response.text
        assert "Terraform" in detail_response.text

    async def test_edit_candidate_clear_skills(
        self,
        client: AsyncClient,
        admin_user: User,
        test_candidate_with_skills: Candidate,
    ):
        """Editing a candidate with empty skills should clear skill tags."""
        client.cookies.update(get_auth_cookie(admin_user))
        response = await client.post(
            f"/candidates/{test_candidate_with_skills.id}",
            data={
                "first_name": test_candidate_with_skills.first_name,
                "last_name": test_candidate_with_skills.last_name,
                "email": test_candidate_with_skills.email,
                "phone": "",
                "linkedin_url": "",
                "skills": "",
                "resume_text": "",
            },
            follow_redirects=False,
        )
        assert response.status_code == 302

    async def test_edit_candidate_preserves_same_email(
        self,
        client: AsyncClient,
        admin_user: User,
        test_candidate: Candidate,
    ):
        """Editing a candidate without changing email should succeed."""
        client.cookies.update(get_auth_cookie(admin_user))
        response = await client.post(
            f"/candidates/{test_candidate.id}",
            data={
                "first_name": "Updated First",
                "last_name": "Updated Last",
                "email": test_candidate.email,
                "phone": "+1-555-777-6666",
                "linkedin_url": "",
                "skills": "NewSkill1, NewSkill2",
                "resume_text": "Updated resume.",
            },
            follow_redirects=False,
        )
        assert response.status_code == 302

        # Verify changes on detail page
        location = response.headers.get("location", "")
        detail_response = await client.get(location)
        assert detail_response.status_code == 200
        assert "Updated First" in detail_response.text
        assert "Updated Last" in detail_response.text


@pytest.mark.asyncio
class TestCandidateSkillManagement:
    """Tests for skill tag management during candidate CRUD."""

    async def test_new_skills_created_on_candidate_create(
        self,
        client: AsyncClient,
        admin_user: User,
        db_session: AsyncSession,
    ):
        """Creating a candidate with new skill names should create Skill records."""
        from sqlalchemy import select

        client.cookies.update(get_auth_cookie(admin_user))
        response = await client.post(
            "/candidates",
            data={
                "first_name": "SkillTest",
                "last_name": "Creator",
                "email": "skilltest.creator@example.com",
                "phone": "",
                "linkedin_url": "",
                "skills": "UniqueSkillAlpha, UniqueSkillBeta",
                "resume_text": "",
            },
            follow_redirects=False,
        )
        assert response.status_code == 302

        # Verify skills were created in the database
        result = await db_session.execute(
            select(Skill).where(Skill.name == "UniqueSkillAlpha")
        )
        skill = result.scalars().first()
        assert skill is not None
        assert skill.name == "UniqueSkillAlpha"

    async def test_existing_skills_reused_on_candidate_create(
        self,
        client: AsyncClient,
        admin_user: User,
        test_skills: list[Skill],
        db_session: AsyncSession,
    ):
        """Creating a candidate with existing skill names should reuse Skill records."""
        from sqlalchemy import select, func

        # Count existing Python skills
        count_before = await db_session.execute(
            select(func.count(Skill.id)).where(Skill.name == "Python")
        )
        before = count_before.scalar() or 0

        client.cookies.update(get_auth_cookie(admin_user))
        response = await client.post(
            "/candidates",
            data={
                "first_name": "SkillReuse",
                "last_name": "Test",
                "email": "skillreuse.test@example.com",
                "phone": "",
                "linkedin_url": "",
                "skills": "Python",
                "resume_text": "",
            },
            follow_redirects=False,
        )
        assert response.status_code == 302

        # Verify no duplicate skill was created
        count_after = await db_session.execute(
            select(func.count(Skill.id)).where(Skill.name == "Python")
        )
        after = count_after.scalar() or 0
        assert after == before


@pytest.mark.asyncio
class TestCandidateAuditLogging:
    """Tests for audit log entries on candidate operations."""

    async def test_create_candidate_creates_audit_log(
        self,
        client: AsyncClient,
        admin_user: User,
        db_session: AsyncSession,
    ):
        """Creating a candidate should create an audit log entry."""
        from sqlalchemy import select
        from app.models.audit_log import ActivityLog

        client.cookies.update(get_auth_cookie(admin_user))
        response = await client.post(
            "/candidates",
            data={
                "first_name": "Audit",
                "last_name": "Test",
                "email": "audit.test@example.com",
                "phone": "",
                "linkedin_url": "",
                "skills": "",
                "resume_text": "",
            },
            follow_redirects=False,
        )
        assert response.status_code == 302

        # Check audit log
        result = await db_session.execute(
            select(ActivityLog).where(
                ActivityLog.action == "create_candidate",
                ActivityLog.user_id == admin_user.id,
            )
        )
        log_entry = result.scalars().first()
        assert log_entry is not None
        assert log_entry.entity_type == "candidate"
        assert "Audit Test" in (log_entry.details or "")

    async def test_edit_candidate_creates_audit_log(
        self,
        client: AsyncClient,
        admin_user: User,
        test_candidate: Candidate,
        db_session: AsyncSession,
    ):
        """Editing a candidate should create an audit log entry."""
        from sqlalchemy import select
        from app.models.audit_log import ActivityLog

        client.cookies.update(get_auth_cookie(admin_user))
        response = await client.post(
            f"/candidates/{test_candidate.id}",
            data={
                "first_name": "AuditEdit",
                "last_name": "TestEdit",
                "email": test_candidate.email,
                "phone": "",
                "linkedin_url": "",
                "skills": "",
                "resume_text": "",
            },
            follow_redirects=False,
        )
        assert response.status_code == 302

        # Check audit log
        result = await db_session.execute(
            select(ActivityLog).where(
                ActivityLog.action == "update_candidate",
                ActivityLog.user_id == admin_user.id,
                ActivityLog.entity_id == test_candidate.id,
            )
        )
        log_entry = result.scalars().first()
        assert log_entry is not None
        assert log_entry.entity_type == "candidate"
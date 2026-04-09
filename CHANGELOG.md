# Changelog

All notable changes to the TalentFlow ATS project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [1.0.0] - 2025-01-01

### Added

#### Authentication
- User registration with email and password
- Secure login and logout with JWT-based session management
- Password hashing using bcrypt for secure credential storage
- Token refresh mechanism for seamless session continuity
- Password reset functionality via email verification

#### Role-Based Access Control (RBAC)
- Predefined roles: Super Admin, Hiring Manager, Recruiter, Interviewer, Read-Only
- Granular permission enforcement across all API endpoints
- Role assignment and management by administrators
- Route-level and resource-level authorization checks

#### Job Management
- Create, update, and archive job postings with detailed descriptions
- Job status lifecycle: Draft, Open, On Hold, Closed
- Department and location categorization for job listings
- Rich text support for job descriptions and requirements
- Job listing search and filtering capabilities

#### Candidate Management
- Candidate profile creation with contact details and metadata
- Resume and document upload with file storage integration
- Candidate search with filters for skills, experience, and status
- Candidate profile viewing with full application history
- Duplicate candidate detection and merge support

#### Application Pipeline
- Multi-stage application pipeline: Applied, Screening, Interview, Offer, Hired, Rejected
- Drag-and-drop style stage progression for applications
- Application status tracking with timestamp history
- Bulk application actions for efficient pipeline management
- Configurable pipeline stages per job posting
- Rejection reason tracking and candidate communication

#### Interview Scheduling
- Interview creation with date, time, and location details
- Interviewer assignment with availability management
- Interview feedback and scorecard submission
- Calendar integration support for scheduling coordination
- Interview round tracking across multiple stages
- Automated interview reminder notifications

#### Dashboards
- Recruiter dashboard with active jobs and pipeline overview
- Hiring manager dashboard with team hiring metrics
- Admin dashboard with system-wide analytics and user management
- Key performance indicators: time-to-hire, pipeline conversion rates
- Visual charts and graphs for hiring funnel analysis
- Real-time data refresh for up-to-date reporting

#### Audit Trail
- Comprehensive logging of all user actions across the system
- Timestamped audit entries with user identification
- Entity-level change tracking for jobs, candidates, and applications
- Filterable audit log viewer for administrators
- Data integrity verification through immutable audit records

#### Responsive UI
- Mobile-first responsive design using Tailwind CSS
- Consistent navigation with sidebar and header components
- Accessible form components with validation feedback
- Toast notifications for user action confirmations
- Loading states and skeleton screens for async operations
- Dark mode support via Tailwind CSS dark variant classes

#### API & Infrastructure
- RESTful API built with FastAPI and async SQLAlchemy
- Pydantic v2 schemas for request and response validation
- SQLite database with async support via aiosqlite
- Alembic database migrations for schema versioning
- CORS middleware configuration for frontend integration
- Structured logging throughout the application
- Environment-based configuration using Pydantic Settings
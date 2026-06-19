# Service Architecture

StudentsCompass services are now grouped by product domain under
`app/services/<domain>/`.

## Domains

- `accounts`: user, profile, and questionnaire services.
- `admin`: admin panel services and admin guards.
- `ai`: AI usage, AI rate limiting, and CV analysis workflows.
- `analytics`: capstone analytics, seed catalog, and embedding services.
- `applications`: application and dashboard workflows.
- `companies`: company, recruiter, and applicant workflows.
- `community`: communities, posts, friendships, and messages.
- `jobs`: job posting, job search, and interview scheduling workflows.
- `notifications`: email notification services.
- `resources`: learning resource and lesson-content services.
- `resumes`: resume storage records and resume course audit workflows.
- `roadmaps`: roadmap services and seed data.
- `storage`: storage providers and media upload services.

## Import Policy

Services should be imported from their domain package, for example:

```python
from app.services.analytics.capstoneAnalyticsService import CapstoneAnalyticsService
from app.services.resumes.resumeService import ResumeService
```

Root-level service modules such as `app.services.resumeService` have been
removed. This keeps the service layer organized by product capability instead of
by a flat list of files.

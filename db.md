# Database Tables and Sync Workflow

## Database Overview

The database is PostgreSQL in Supabase. The initial migration creates four tables:
`jobs`, `candidates`, `applications`, and `interviews`.

The follow-up migration adds Google Forms response tracking to `applications`.
A later migration replaces numeric compensation bounds with text-based job criteria.

### Enums

- `job_status`: `draft`, `posted`, `closed`
- `application_stage`: `sync_evaluation`, `technical_interview`, `ceo_review`, `closed`
- `screening_decision`: `pass`, `fail`
- `pipeline_status`: `failed_at_sync`, `active_pipeline`, `pending_ceo_decision`, `closed_complete`
- `final_decision`: `pending`, `pass`, `fail`
- `interview_status`: `pending`, `complete`

### `jobs`

One row per vacancy.

| Column | Meaning |
| --- | --- |
| `id` | Primary key, UUID |
| `title` | Job title |
| `tech_stack`, `seniority` | Role requirements |
| `required_experience` | Required experience text |
| `salary` | Optional salary text |
| `location` | Optional location |
| `work_type` | Optional work arrangement, such as remote or on-site |
| `university` | Optional university criterion |
| `jd_markdown` | Job description used for screening |
| `google_form_id`, `google_form_url` | Linked application form |
| `linkedin_blurb` | Job-post text |
| `status` | Draft, posted, or closed |
| `created_at` | Creation timestamp |

### `candidates`

One global profile per person. A candidate may apply to multiple jobs.

| Column | Meaning |
| --- | --- |
| `id` | Primary key, UUID |
| `full_name`, `email` | Candidate identity |
| `phone`, `linkedin_url` | Optional identity details |
| `created_at` | Creation timestamp |

Email is unique without regard to letter case. Phone and LinkedIn have lookup indexes but are not unique.

### `applications`

One candidate’s application to one job. This table holds the screening outcome and the original form answers.

| Column | Meaning |
| --- | --- |
| `id` | Primary key, UUID |
| `candidate_id` | Foreign key to `candidates.id` |
| `job_id` | Foreign key to `jobs.id` |
| `current_stage` | Current recruitment stage |
| `agent_decision` | AI screening result: pass or fail |
| `screening_summary` | AI-generated screening summary |
| `hr_override_status` | HR screening override, if any |
| `examiner` | Who examined the application |
| `pipeline_status` | Pipeline state |
| `final_decision` | Pending, pass, or fail |
| `remarks` | Human-authored remarks |
| `google_form_response_id` | Google response ID used for sync deduplication |
| `form_responses` | Original question titles and answers, stored as JSONB |
| `created_at` | Creation timestamp |

The `(candidate_id, job_id)` pair is unique, so a candidate profile cannot have two applications for the same job. During sync, an applicant is also considered a duplicate for that job if any one of their email, phone, or LinkedIn URL values matches an existing applicant on the job. A PostgreSQL trigger enforces this identity rule atomically for concurrent inserts. The `(job_id, google_form_response_id)` pair is unique when the response ID is present, so the same Google response cannot be imported twice for that job.

### `interviews`

One row per scheduled interview round.

| Column | Meaning |
| --- | --- |
| `id` | Primary key, UUID |
| `application_id` | Foreign key to `applications.id` |
| `sequence_order` | Round number |
| `scheduled_at`, `interview_date` | Schedule information |
| `local_audio_path` | Path to the locally stored recording |
| `feedback` | Interview feedback |
| `status` | Pending or complete |
| `created_at` | Creation timestamp |

Each application can have only one interview for a given `sequence_order`.

### Dashboard views

- `hr_passed_candidates_dashboard` shows applications in the active or CEO-decision pipeline with a pending final decision.
- `hr_failed_candidates_dashboard` shows applications rejected during sync that have not been restored by HR.

## Google Forms Sync Workflow

1. HR starts sync for a job. The backend checks that the job exists and has a job description and linked Google Form.
2. The backend uses the job’s `google_form_id` to call the Google Forms API. It fetches responses in pages of 20, following each `nextPageToken` until Google returns no next-page token. This API pagination is automatic and separate from the applicant-list Previous/Next controls in the UI.
3. Each cloned form includes Full Name, Email Address, Contact Number, and LinkedIn URL questions when the template or generated questions do not already provide them. Email Address remains required because the candidate profile requires email. The copied template supplies the résumé upload question. The backend maps answer question IDs to question titles and extracts identity fields from those answers (or Google’s respondent email when available).
4. For each response, it checks whether that response ID is already stored for this job. Already imported responses are skipped.
5. It checks email, phone, and LinkedIn independently against applicants for this job, even if another required field is missing. A match on any one field marks the response as a duplicate. Otherwise, it validates the required name/email and matches or creates the global candidate profile.
6. The backend downloads uploaded PDF résumés from Google Drive and extracts text for screening. It does not save a local résumé copy. Candidate name and email are anonymized in the text sent to the AI screener.
7. If screening succeeds, the backend creates a candidate profile if needed, then creates an application containing the response ID, original answers, AI decision, and screening summary.
8. A screening pass sets `pipeline_status = active_pipeline` and `final_decision = pending`. A screening fail sets `pipeline_status = failed_at_sync` and `final_decision = fail`.
9. The sync result reports responses as synced, duplicates, or errors. A later sync can retry responses that did not result in a saved application.

## Where the sync gets its data

Google Forms is the source of applicant responses; Supabase is where successfully processed applications are stored. The backend reads the form ID from the `jobs` row, fetches responses from Google, then writes candidate and application records to Supabase.

The backend needs Google credentials configured through `GOOGLE_OAUTH_CLIENT_FILE` and `GOOGLE_OAUTH_TOKEN_FILE`, or `GOOGLE_SERVICE_ACCOUNT_FILE`. Those credentials must have access to the form and uploaded files, including the `forms.responses.readonly` permission for sync.

## Implementation note

The code declares the `forms.responses.readonly` scope, but the response-fetch method currently initializes Google services using the default scopes, which omit that read scope. Sync may require passing the response-read scope when building the Google service.
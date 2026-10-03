# Completed Work

## Current Status

Stages 1–3 and Stage 4 are complete: the database migration was applied to Supabase; Pydantic schemas, local recording/anonymization utilities, centralized prompts, the provider-neutral Gemini adapter, tested Supabase CRUD modules, Google Forms integration, local-media service wrapper, FastAPI feature routes, and the portfolio jobs dashboard are implemented.

### New additions
- A jobs dashboard page now lists every hiring requisition as a status card and lets HR drill into applicant details for the selected job.
- Applicant dashboard drilldowns now list only jobs with applicants matching the selected card and show the relevant per-job applicant count.
- Dashboard detail back controls use same-tab Streamlit navigation instead of opening URL links in a new tab.
- Dashboard applicant cards now filter jobs by their own matching count: total, Stage 1, first interview, second interview, CEO review, hired, and CEO-failed.
- Job selectors show lifecycle dates and applicant counts. `created_at`, `posted_at`, and `closed_at` are tracked separately.
- Selecting an applicant opens a dedicated Candidate Detail page. Full application data is loaded through the dossier endpoint, form questions are expandable, unanswered questions show `Answer not provided`, and browser/in-app back navigation preserves the active filter.
- Applicant views support filters for pass, fail, pending, and free-text search by name, email, or application ID.
- HR can remove any interview round from a candidate’s pipeline; the remaining rounds are automatically reindexed to keep sequence numbers contiguous.

## 1. Database Foundation

Migration: `supabase/migrations/20260928000000_init_recruitment_schema.sql`

It creates `jobs`, `candidates`, `applications`, and `interviews`, with typed status fields, foreign keys, indexes, and the HR dashboard views.

- `UNIQUE(candidate_id, job_id)` prevents one candidate from applying twice to the same job, while allowing applications to other jobs.
- `UNIQUE(application_id, sequence_order)` prevents duplicate interview round numbers on one application.
- A new application defaults to `pipeline_status=failed_at_sync` until sync explicitly records its result. Passing sync sets `active_pipeline` and `final_decision=pending`; failing sync sets `failed_at_sync` and `final_decision=fail`.
- The passed dashboard shows active/pending applications that can proceed. The failed dashboard shows sync failures that have not been restored by HR.
- Row Level Security is enabled on the four tables. The backend must access them through its server-side Supabase service credentials unless user-specific policies are added later.

## 2. Data Validation

Schemas are in `backend/app/schemas/` and use Pydantic v2. They reject unknown fields so unexpected data, including transcript or model-reasoning fields, cannot silently pass through.

- Job inputs require non-empty title, tech stack, and seniority. Compensation must be non-negative and the minimum cannot exceed the maximum when both values are supplied. A patch must contain at least one field.
- Candidate creation requires a valid email and non-empty name. Identity lookup must include at least one of email, phone, or LinkedIn URL.
- Screening results require a `pass` or `fail` decision and a concise summary. HR override requests require a non-empty HR username.
- Interview scheduling requires a timezone-aware date and time. The server assigns round numbers and local paths; clients cannot supply them. Round numbers must be positive.
- Interview updates must include at least one field. No schema accepts transcript or audio-analysis data.

Invalid schema input raises a Pydantic `ValidationError`; FastAPI returns HTTP 422 for invalid request data.

## 3. Local Interview Recordings

`backend/app/config.py` reads `RECORDINGS_DIR` from the environment. Its default is the repository's `backend/recordings` directory. Relative overrides resolve from the repository root; a deployment can supply an absolute mounted-volume path.

For example, round 2 is written under:

```text
{RECORDINGS_DIR}/Data_Engineer/Alex_Doe/20261001/technical_interview_2.mp3
```

`backend/app/utils/file_handler.py` converts unsafe characters in job and candidate names to safe path segments, checks the resolved path stays inside the configured root, and writes with exclusive-create mode so an existing round file is never replaced.

**Recording passes verification when** the expected path is inside the configured root, has an `.mp3` extension, points to a regular file, and the file is non-empty. Empty uploads are removed and raise `ValueError`; an existing destination raises `FileExistsError`. Verification returns `False` for missing, empty, invalid, or out-of-root paths. Audio bytes are not decoded or inspected, so this verifies storage, not audio encoding or quality.

## 4. Applicant Text Anonymization

`backend/app/utils/anonymizer.py` replaces the supplied candidate name, age, and gender with `[NAME]`, `[AGE]`, and `[GENDER]` before screening. Matching is case-insensitive; name matching tolerates repeated whitespace. Labeled age/gender fields are also redacted. Unrelated information, such as years of experience, is preserved.

**Input errors:** text must be a string, full name must be non-empty, age must be a non-negative integer or `None`, and gender must be a string or `None`. The utility only redacts the supplied values and recognized labeled fields; it does not discover arbitrary aliases or infer personal details.

## 5. Centralized Text Prompts

Prompt instructions live in `backend/app/prompts/`, separate from API endpoints and independent of any provider SDK.

- `jd_prompts.py` accepts a validated `JobCreate` model and serializes its criteria as JSON. The instructions require editable Markdown and prohibit inventing requirements, company details, or compensation.
- `screen_prompts.py` serializes the job description, anonymized résumé, and form responses as JSON. Candidate text is treated as untrusted data, not as instructions. The screening rules compare evidence only to stated requirements and return only `agent_decision` (`pass` or `fail`) and a concise `screening_summary`.
- Missing evidence for a must-have requirement is summarized for HR as insufficient evidence. HR retains override authority. The prompts do not request private reasoning or analyze interview audio.

These modules prepare instructions and input payloads; provider calls stay in the provider-neutral service layer described below.

## 6. Provider Integration

`backend/app/services/ai/base.py` defines `TextAIProvider`, a provider-neutral interface for plain text and Pydantic-validated structured results. It also defines configuration, request, and response errors without exposing vendor-specific exceptions to callers.

`backend/app/services/ai/gemini_flash.py` implements that interface with Google's `google-genai` SDK. The API key is read from global settings as a secret; the model is selected by `GEMINI_MODEL`, defaulting to the stable text model `gemini-3.1-flash-lite`. The official catalog does not list an exact `gemini-3.1-flash` text model. Gemini calls use `store=False`; screening output is validated against `ApplicationScreeningResult`. Empty or malformed outputs and SDK failures raise provider-neutral errors and cannot become an implicit pass.

No real API request was made during testing because no project key was available. The SDK client and method surface were smoke-tested offline, and request behavior was tested with a fake client.

## 7. Supabase CRUD

`backend/app/services/supabase_service.py` lazily initializes the Supabase client from `SUPABASE_URL` and `SUPABASE_SERVICE_ROLE_KEY` in global settings. Importing CRUD does not require credentials; the first database operation raises a configuration error if they are missing. Keep the service-role key on the backend only.

The modules under `backend/app/database/crud/` own all database calls. They create/read/list/update jobs; match candidates using email, phone, or LinkedIn; reject conflicting multi-key matches; create and find job applications; assemble application history; apply HR pass overrides only to sync-failed applications; read both dashboard views; schedule numbered interview rounds; update round details; and persist recording references only after checking the file, root, and round sequence.

Database and dashboard rows are validated by the existing Pydantic schemas. Supabase exceptions are wrapped in a safe `DatabaseOperationError` rather than returning provider payloads that may contain candidate data.

## 8. Verification

`backend/app/prompts/form_prompts.py` prepares a question-generation request from validated job criteria. Gemini returns a typed, job-specific question set; question wording is not selected from a fixed list. Supported Google Forms types are short text, paragraph, multiple choice, and checkbox. Choice questions require at least two unique options. The cloned template retains its résumé-upload question, and generated questions are appended to the copy.

`backend/app/services/google_forms.py` lazily loads a service-account credential file when called, copies the configured Drive template, updates its title, appends typed question items, and returns a validated Form ID and responder URL. API errors are sanitized; a partially created copy is deleted on later failure. No live Google API request was made during tests.

`backend/app/services/local_media_service.py` connects an interview upload to the existing local save/verify utility. It stores bytes without decoding or inspecting audio and returns the verified path and interview ID/round metadata.

Tests are in `backend/tests/`. The suite covers schema acceptance/rejection, candidate identity checks, schedule rules, path sanitization, traversal protection, no-overwrite behavior, empty-file cleanup, anonymization, prompt input/output contracts, provider behavior, structured response validation, CRUD behavior using a fake Supabase client, and Google/local-media services using fakes and temporary folders. Google Forms parsing also retains unanswered question titles. Migration `supabase/migrations/20261002000009_dashboard_job_filter_counts.sql` adds card-specific job counts and lifecycle timestamps.

Run from the repository root using the backend virtual environment:

```powershell
.\backend\.venv\Scripts\python.exe -m unittest discover -s .\backend\tests -v
```

The frontend is also started from the backend venv environment when using this project setup:

```powershell
.\backend\.venv\Scripts\python.exe -m streamlit run frontend\main.py --server.port 8502
```

The FastAPI app exposes `GET /health` and the implemented feature routes under `/api/v1`, including jobs, form sync, candidate history, interviews, and final decisions.

Latest result: **111 passed, 1 unrelated failure out of 112 tests**. The failure is the existing Windows path-normalization assertion in `backend/tests/test_utils.py`. CRUD behavior is tested with fake clients. The local app has also successfully generated Gemini content and synced a PDF submission from Google Forms. Starlette emits a deprecation warning about its current HTTPX test-client integration.

## Remaining Work

Interview audio remains local-only and is never transcribed or analyzed. Supabase/RLS behavior still needs environment-backed smoke testing. Docker remains intentionally deferred.

## 9. Automatic Google Forms Sync

The HR sync action now retrieves all response pages from the job-specific Google Form. Each response is mapped to question titles, uploaded PDFs are downloaded from Drive using the binary media API, and the résumé plus all answers are screened independently. PDFs remain in Drive; they are not saved locally. Required name/email fields are added when cloning a form if the template/generated questions do not already collect them. Original answers are saved on the application, the template's `Contact Number` answer maps to candidate phone, and name/email are redacted from AI-bound screening text.

The application table stores each Forms response ID with a per-job unique index, so repeat syncs skip previously imported responses. Global email/phone/LinkedIn matching and the `(candidate_id, job_id)` unique constraint continue to enforce cross-job identity and same-job non-redundancy. The applicant table shows name, email, phone, screening outcome, and summary; selecting a row shows the full original answers and prior applications. History displays AI screening summaries separately from human remarks; CEO final-decision remarks are human-authored. Generated JD and LinkedIn content is copied into its editor immediately after generation.

Migrations `supabase/migrations/20260930000000_add_form_submission_data.sql` through `supabase/migrations/20261002000009_dashboard_job_filter_counts.sql` support the current form-sync and dashboard workflows. The latest migration adds per-card per-job applicant counts, `posted_at`/`closed_at`, and lifecycle timestamp triggers. The repeatable `supabase/seed.sql` covers all dashboard cards with fictional records. Only response sync requires `forms.responses.readonly`; OAuth users with older tokens are prompted to re-consent when they first sync, while form cloning continues with Drive and Forms body scopes. The local app has successfully synced and screened a PDF submission.
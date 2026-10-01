# DataRopes Recruitment Tool: Engineering Handoff

This file is the current implementation handoff. It is intended to give the next engineer enough context to continue without relying on chat history. The roadmap source remains `plan.md`; product behavior is specified in `spec.md`; the file tree is in `project_structure.text`.

## Current Checkpoint

- Stages 1 through 5 are complete.
- The next planned work is Stage 6, containerization and orchestration.
- The full backend test suite last passed **92 tests** with `backend/.venv`.
- Automated tests use fake Gemini, Supabase, Drive, and Forms clients. The local app has successfully generated Gemini content and synced a Google Forms PDF submission.
- The Supabase migration was applied using the Supabase CLI, which reported success. The schema was not separately queried after that push in this workspace.

## Architecture Rules

- Streamlit calls FastAPI using `BACKEND_API_URL`; browser/frontend code must not hold backend secrets.
- FastAPI routers are thin. Validate request/response data with Pydantic schemas, then delegate to services and CRUD.
- All database reads, writes, transactions, and view lookups live under `backend/app/database/crud/`.
- CRUD modules import the lazy client from `backend/app/services/supabase_service.py`.
- AI prompts live in `backend/app/prompts/`. Provider-specific SDK calls live behind `backend/app/services/ai/base.py` and its adapters.
- Interview recordings are stored locally only. Never transcribe, slice, decode, or semantically analyze audio in this prototype.

## Stage 1: Foundation

### Phase 1.1: Supabase Migration

`supabase/migrations/20260928000000_init_recruitment_schema.sql` creates:

- `jobs`, `candidates`, `applications`, and `interviews` tables with Postgres enums, foreign keys, defaults, checks, and indexes.
- `UNIQUE(candidate_id, job_id)` to block duplicate submissions to the same job while allowing a candidate to apply to other jobs.
- `UNIQUE(application_id, sequence_order)` to prevent duplicate interview round numbers within one application.
- `hr_passed_candidates_dashboard` and `hr_failed_candidates_dashboard` views.
- RLS on all four tables. Backend access is expected through the server-side service client; do not expose the service-role key to frontend code.

New applications default fail-closed to `pipeline_status=failed_at_sync`; the sync operation must explicitly persist the matching state: pass becomes `active_pipeline` and `final_decision=pending`, fail becomes `failed_at_sync` and `final_decision=fail`.

### Phase 1.2: Pydantic Schemas

Schemas are in `backend/app/schemas/`; Pydantic v2 models reject unknown fields. They cover jobs, candidates, applications, screening results, history, overrides, interview rounds, and interview recording results. Input checks include email validation, minimum candidate identity keys, non-empty job fields, valid compensation ranges, timezone-aware schedules, and server-controlled round/path values. No transcript or model chain-of-thought fields are accepted.

### Phase 1.3: Local Media and Anonymization

- `backend/app/config.py` reads `RECORDINGS_DIR`, defaulting to `backend/recordings` under the repository root; absolute mounted-volume paths are supported.
- `backend/app/utils/file_handler.py` sanitizes job/candidate path segments, prevents traversal outside the configured root, saves exclusively (never overwrites), and verifies a regular, non-empty `.mp3` file. Verification checks storage only, not audio validity.
- Expected path: `{RECORDINGS_DIR}/{job_title}/{candidate_name}/{YYYYMMDD}/technical_interview_{sequence_order}.mp3`.
- `backend/app/utils/anonymizer.py` replaces supplied name, age, and gender values with neutral markers and preserves unrelated experience text. It does not discover every possible alias or infer personal details.

## Stage 2: Prompts and Gemini

### Phase 2.1: Central Prompts

- `backend/app/prompts/jd_prompts.py` takes a validated `JobCreate` model and builds JSON context for factual, editable Markdown JD generation. The prompt prohibits inventing criteria or compensation.
- `backend/app/prompts/screen_prompts.py` takes a job description plus anonymized résumé and form text. Applicant text is untrusted data, not instructions. The model returns only `agent_decision` and a concise `screening_summary`; missing must-have evidence is described for HR. No private chain-of-thought is requested.
- `backend/app/prompts/form_prompts.py` takes validated job criteria and instructs Gemini to generate a dynamic, role-specific question set. There is no fixed global list of question texts.

### Phase 2.2: Provider Adapter

- `backend/app/services/ai/base.py` defines provider-neutral `TextAIProvider` operations and provider-neutral error classes.
- `backend/app/services/ai/gemini_flash.py` implements text and typed structured generation with `google-genai`.
- `GEMINI_API_KEY` and `GEMINI_MODEL` are read through global settings. Default text model is `gemini-3.1-flash-lite`; the official model catalog does not list an exact `gemini-3.1-flash` text model.
- Gemini requests use `store=False`. Structured responses are Pydantic-validated; empty/malformed responses and provider errors fail closed.
- No real Gemini request has been made; the adapter is fake-client tested and its SDK surface was smoke-tested without a network call.

## Stage 3: CRUD and External Services

### Phase 3.1: Supabase CRUD

- `backend/app/services/supabase_service.py` exposes a thread-safe lazy client. Importing it needs no credentials; the first DB operation requires `SUPABASE_URL` and `SUPABASE_SERVICE_ROLE_KEY`.
- `backend/app/database/crud/errors.py` wraps database failures without echoing provider response/candidate data and defines `AmbiguousCandidateMatchError`.
- `jobs_db.py`: create/get/list/update jobs.
- `candidates_db.py`: create and identity-match candidates; create/get applications; list job applications; assemble history; read passed/failed views; apply HR pass override only to applications still at `failed_at_sync`.
- Candidate identity matching checks all supplied keys. If they resolve to different candidate IDs, it raises an ambiguity error; it never merges profiles.
- `interviews_db.py`: list/schedule rounds, update round fields, and persist a recording reference only after verifying file root, non-empty file, expected sequence-specific filename, interview ID, and DB sequence.
- CRUD uses Pydantic models for returned DB/view rows. All query execution stays inside CRUD.
- These functions have only been tested against fake Supabase clients. Live connectivity and RLS behavior have not been smoke-tested.

### Phase 3.2: Google Forms and Local Media

- `backend/app/schemas/google_forms_schema.py` defines typed `GoogleFormQuestion`, `GoogleFormQuestionSet`, `GoogleFormCloneRequest`, and `GoogleFormCloneResult` models. Supported types: `short_text`, `paragraph`, `multiple_choice`, `checkbox`. Choice questions require at least two unique options.
- Gemini question generation is based on each validated job's criteria. Question texts vary by vacancy; the supported type/validation shape is fixed. The résumé-upload item is already in the source Form template and is retained.
- `backend/app/services/google_forms.py` lazily uses a service-account file (`GOOGLE_SERVICE_ACCOUNT_FILE`), Drive template ID (`GOOGLE_FORM_TEMPLATE_ID`), and optional destination folder (`GOOGLE_DRIVE_FOLDER_ID`). It copies the template, updates the title, appends generated questions using Forms API, fetches and validates the responder URL, and cleans up a partially created copy after later API failure.
- The service returns the Form ID and responder URL. It **does not yet save them to the job row or create/publish a job post**. Phase 4.2 must wire those actions through CRUD and include the job-specific responder URL in the reviewed post.
- `backend/app/services/local_media_service.py` wraps the local file handler and returns verified path/round metadata without inspecting audio bytes.
- No live Google API call or real service-account credential was used in tests.

## Stage 4: FastAPI

### Phase 4.1: Framework Assembly

- `backend/app/main.py` creates the FastAPI app.
- `backend/app/api/router.py` assembles the root API router, `/health`, and an empty `/api/v1` router reserved for feature endpoints.
- `backend/app/schemas/health_schema.py` validates `{"status":"ok"}`.
- `/health` does not contact Supabase, Gemini, or Google, so it works without external credentials.
- `backend/tests/test_api.py` covers health and router basics. The FastAPI TestClient currently emits a Starlette deprecation warning for its HTTPX transport, but tests pass.

### Phase 4.2: Completed

Thin, Pydantic-validated routes from `spec.md` now wire the existing services and CRUD:

1. Job creation, JD generation/editing, form cloning, and LinkedIn blurb generation.
2. Candidate sync with anonymization, typed screening, duplicate-job protection, history, application listing, and HR override.
3. Numbered interview scheduling, feedback updates, round-specific multipart recording upload, local verification, and database reference persistence.
4. CEO dossier, move-to-review guard, and final-decision routes.

The LinkedIn route requires both a saved JD and the cloned job-specific responder URL. Interview audio is never sent to Gemini.

Before code, compare every new endpoint request/response with the spec; if its path or schema must change, update `spec.md`, `Agents.md`, or `project_structure.text` first. Add fake-service/router tests before implementation and rerun the full backend suite.

### Automatic Form Sync Update

The HR sync endpoint now has no applicant request body: it retrieves all pages of responses from the linked form, downloads uploaded PDFs through Drive's binary media endpoint, extracts their text, screens each submission with its complete answer set, and returns per-response outcomes. PDFs stay in Google Drive; the backend does not save a local résumé copy. Cloned forms include required name/email fields if the template or generated questions do not already provide them. Applications retain original answers and the form response ID; a unique per-job index makes repeat syncs idempotent. The template's `Contact Number` answer is mapped to the candidate phone field. Applicant listings include candidate name, email, phone, and saved answers. Candidate history returns prior screening summaries separately from human remarks; the CEO final-decision action writes human remarks.

Migration `supabase/migrations/20260930000000_add_form_submission_data.sql` was applied to the configured Supabase project. Only response sync requires the `forms.responses.readonly` scope; users with older OAuth tokens are prompted to consent when they first sync. Form cloning continues to use Drive and Forms body scopes. The full backend suite passes 92 tests; the local app's PDF sync flow has been confirmed.

## Stage 5 Completed Locally

The Streamlit frontend is implemented as a multipage app:

- `frontend/main.py`: command center.
- `frontend/pages/1_🎯_Hiring_Request.py`: job setup, JD, Google Form, and LinkedIn post.
- `frontend/pages/2_🔄_Sync_&_Screen.py`: applicant sync, pool filters, and HR overrides.
- `frontend/pages/3_🎙️_Interviews.py`: numbered rounds, scheduling, feedback, MP3 upload, and the HR hand-off to CEO review after all rounds are complete.
- `frontend/pages/4_💼_Executive.py`: CEO dossier review and final decision.
- `frontend/ui.py`: shared styling and REST client.

Generated JD and LinkedIn text is copied into the corresponding Streamlit editor state immediately after generation. The sync page shows candidate phone, selected-applicant form answers, and prior screening summaries separately from human remarks. Its sync-run table reports the latest run; the applicant table lists persisted applications for the selected job.

The frontend has its own environment at `frontend/.venv`; Docker is not required for local testing.

### Local Run Commands

From the repository root, start the backend in one terminal:

```powershell
backend\.venv\Scripts\python.exe -m uvicorn backend.app.main:app --reload --host 127.0.0.1 --port 8000
```

Start the frontend in another terminal:

```powershell
frontend\.venv\Scripts\python.exe -m streamlit run frontend\main.py --server.port 8502
```

Open `http://localhost:8502`. The UI calls `http://localhost:8000` by default; set `BACKEND_API_URL` to change it.

### Local Environment Variables

Required for the backend workflows:

- `GEMINI_API_KEY`: required for JD generation, form-question generation, LinkedIn copy, and applicant screening.
- `SUPABASE_URL`: Supabase project URL.
- `SUPABASE_SERVICE_ROLE_KEY`: server-only Supabase service-role key; never expose it to Streamlit/browser code.

Required only for Google Form cloning:

- `GOOGLE_SERVICE_ACCOUNT_FILE`: readable service-account JSON path.
- `GOOGLE_FORM_TEMPLATE_ID`: Drive/Form template containing the résumé upload item.
- `GOOGLE_DRIVE_FOLDER_ID`: optional destination folder.

For a personal Gmail account, use OAuth instead of the service account:

1. Enable Drive API and Forms API in Google Cloud Console.
2. Configure the OAuth consent screen and add the Gmail account as a test user.
3. Create an OAuth client of type **Desktop app** and download its JSON file.
4. Save it as `credentials/google-oauth-client.json`.
5. Set `GOOGLE_OAUTH_CLIENT_FILE=./credentials/google-oauth-client.json` and `GOOGLE_OAUTH_TOKEN_FILE=./credentials/google-oauth-token.json`.
6. On the first form action, sign in in the browser as the Gmail account that owns or can edit the template and destination folder. The refresh token is cached locally and ignored by Git.

When `GOOGLE_OAUTH_CLIENT_FILE` is set, OAuth takes priority over `GOOGLE_SERVICE_ACCOUNT_FILE`. The service account does not need to be shared with the personal My Drive folder in this mode.

Optional:

- `GEMINI_MODEL`: defaults to `gemini-3.1-flash-lite`.
- `RECORDINGS_DIR`: defaults to `./backend/recordings`.
- `BACKEND_API_URL`: frontend-only API base URL; defaults to `http://localhost:8000`.

## Stage 6 Still Pending

Stage 5 implements Streamlit role routing and screens for hiring setup, screening/overrides, the candidate profile and numbered interview workflow, and executive decisions. Stage 6 adds Dockerfiles and orchestration, passes secrets only through environment configuration, and mounts the local recordings volume.

## Environment and Credential Handling

- Use `backend/.venv` and run tests from the repository root:

```powershell
.\backend\.venv\Scripts\python.exe -m unittest discover -s .\backend\tests -v
```

- `.gitignore` currently excludes `.env`, `**/.env`, venvs, caches, backend recordings, `credentials/`, `secrets/`, and service-account JSON files.
- The user reports that API values in `.env.example` are intentionally truncated. Treat those as placeholders/non-working values. Do not print or copy secrets into this handoff. Use the ignored `.env` for local keys; never commit real Gemini, Supabase service-role, or Google service-account credentials.
- The user says to proceed with current `.env.example`; do not edit it unless asked.

## Last Verified Test State

Last recorded full-suite run: **92 tests passed**. The local app has successfully synced and screened a Google Forms PDF submission. Automated tests still use fake integrations and do not replace environment-backed Supabase/RLS verification.
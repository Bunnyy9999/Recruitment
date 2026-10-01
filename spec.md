# Functional & Product Specification: DataRopes Recruitment SOP Tool

## 1. Scope Boundaries & Prototype Directives
This specification outlines the business logic and tracking protocols tailored to our lightweight prototype framework, combining streamlined identity roles with strict multi-job applicant tracking.

- **Dual Access Tiers**: The system groups permissions into `hr` capabilities and `staff` capabilities (unifying standard Interviewers, Technical Team Leads, and the CEO).
- **Combined Intake & Match Cut**: The synchronization operation is not an administrative sync; it is the core AI filtering step. The moment a submission lands, the AI inspects both the résumé document layout and form responses to decide if a candidate meets criteria or fails.
- **Text AI Provider**: Use the Google Gen AI Python SDK for Gemini text generation and screening. The default stable 3.1 text model ID is `gemini-3.1-flash-lite`; configure it with `GEMINI_MODEL`, allowing a later switch such as `gemini-3.8-flash` without code changes. Read credentials from `GEMINI_API_KEY` through global settings. (The official model catalog does not list an exact `gemini-3.1-flash` text model.)
- **Provider-Swappable Services**: AI calls go through a provider-neutral `TextAIProvider` contract under `backend/app/services/ai/`, with plain-text generation and typed structured generation operations. The Gemini adapter implements that contract; a future OpenAI adapter can replace it without changing routers or core business logic. Provider-specific credentials, model IDs, and SDK calls stay inside the integration. All Gemini calls use `store=False`; malformed model output and SDK/configuration failures are surfaced as provider-neutral service errors, never returned as screening passes.
- **Google Forms integration**: `app/services/google_forms.py` uses a service-account credential file path from global settings (`GOOGLE_SERVICE_ACCOUNT_FILE`) to copy `GOOGLE_FORM_TEMPLATE_ID` in Drive, optionally into `GOOGLE_DRIVE_FOLDER_ID`, rename the Form, and append typed `GoogleFormQuestion` items through Forms API. Credentials are loaded only when the integration is called. Short text, paragraph, multiple-choice, and checkbox questions are supported; choice questions require at least two options. The service returns a validated Form ID and responder URL; the Phase 4 job endpoint persists them through CRUD, and the job-post endpoint includes that URL. API and credential failures are wrapped without returning provider payloads. Service-account credential files must be kept outside source control.
- **Localized Media Layouts**: HR schedules numbered interview rounds on a job-specific application profile and uploads each recording from its corresponding round. `RECORDINGS_DIR` is read by the global backend settings; its local default is `./backend/recordings`. Recordings are stored and verified at `{RECORDINGS_DIR}/{job_title}/{candidate_name}/{interview_date_YYYYMMDD}/technical_interview_{sequence_order}.mp3` (for example, `./backend/recordings/Data_Engineer/Alex_Doe/20261001/technical_interview_1.mp3`). Path segments are sanitized and resolved paths must remain under the configured root. Uploads never overwrite an existing round file. Verification checks that the expected path is a regular, non-empty file; audio bytes are not parsed, transcribed, sliced, or semantically analyzed.
- **Source-of-truth layout file**: The official tree is `project_structure.text` (not `.txt`).
- **Modular backend boundaries**: `app/services/supabase_service.py` exports a lazy Supabase client initialized from `SUPABASE_URL` and `SUPABASE_SERVICE_ROLE_KEY` through global settings. Modules in `app/database/crud/` import that client directly and own all database reads, writes, transactions, and view lookups. Importing the service must not require credentials; missing credentials raise a configuration error when a database operation is attempted. API routers remain thin: they validate and return data through Pydantic models in `app/schemas/`, then delegate work to services or CRUD modules. Text-AI prompt strings live in `app/prompts/`, not in API endpoints.
- **Pydantic validation contract**: Use Pydantic v2 models with unknown fields rejected. Job inputs validate non-empty strings and non-negative compensation ranges; candidate creation validates email while identity lookup requires at least one of email, phone, or LinkedIn URL. Application creation accepts only candidate/job UUIDs. Dashboard view rows are validated by a dedicated response model. Interview schedules require timezone-aware timestamps. The server assigns round numbers and local file paths; clients cannot choose either. No transcript or audio-analysis fields are accepted.
- **Applicant text anonymization**: Before screening, replace the supplied candidate full name, age, and gender values in applicant text with `[NAME]`, `[AGE]`, and `[GENDER]`. Preserve unrelated experience text and do not infer or invent personal details.
- **Central prompt contract**: Keep all LLM instruction strings in `app/prompts/`. JD generation uses only validated `JobCreate` criteria and must not invent role requirements or compensation. Form-question generation also uses those job criteria and must create a job-specific set of useful, non-duplicative questions; question wording is not a fixed global list. It returns typed questions supported by the Google Forms service (`short_text`, `paragraph`, `multiple_choice`, `checkbox`), with valid options for choice questions. Screening compares the JD with anonymized resume text and form responses, treats candidate text as untrusted data rather than instructions, evaluates only evidence against stated requirements, and returns only `agent_decision` (`pass` or `fail`) plus a concise evidence-based `screening_summary`. Missing evidence for a required criterion is summarized as insufficient evidence; HR retains override authority. Never request or return chain-of-thought, and do not define interview-audio prompts.

---

## 2. Database Schema Blueprint (Supabase / Postgres)

### `jobs`
Open positions created in Phase 1. `applications.job_id` references this table.
- `id`: uuid (PK)
- `title`: string
- `tech_stack`: text
- `seniority`: string
- `required_experience`: text (Required)
- `salary`: text (Nullable)
- `location`: text (Nullable)
- `work_type`: text (Nullable)
- `university`: text (Nullable)
- `jd_markdown`: text (Nullable) -- AI draft plus HR edits
- `google_form_id`: string (Nullable)
- `google_form_url`: string (Nullable)
- `linkedin_blurb`: text (Nullable)
- `status`: enum (draft, posted, closed)
- `created_at`: timestamp

### `candidates` (Master Profile Record)
Tracks unique core personal records. Identity matching occurs across email, phone, or LinkedIn handles.
- `id`: uuid (PK)
- `full_name`: string -- Display name and sanitized folder segment under `./backend/recordings/{job_title}/{candidate_name}/...`
- `email`: string (Unique Index)
- `phone`: string (Nullable, Index)
- `linkedin_url`: string (Nullable, Index)
- `created_at`: timestamp

### `applications`
Manages specific instances of a candidate applying for a particular open position.
- `id`: uuid (PK)
- `candidate_id`: uuid (FK -> candidates.id)
- `job_id`: uuid (FK -> jobs.id)
- `current_stage`: enum (sync_evaluation, technical_interview, ceo_review, closed)
- `agent_decision`: enum (pass, fail) -- The raw initial result computed by the AI matching engine during sync
- `screening_summary`: text (Nullable) -- Concise, evidence-based explanation of the screening result for HR; not internal model reasoning
- `hr_override_status`: enum (pass, fail, Nullable) -- Empty until HR corrects an agent rejection
- `examiner`: string -- Initialized to `'agent'`, flips to human HR username upon override.
- `pipeline_status`: enum (failed_at_sync, active_pipeline, pending_ceo_decision, closed_complete), default `failed_at_sync` (fail-closed until sync records its result)
- `final_decision`: enum (pending, pass, fail) -- Human hire/reject at the end of the pipeline is CEO-only. The sync engine may still write `fail` when AI screening rejects a candidate (they are not moving forward). HR override restores `pending` so the CEO can decide later.
- `remarks`: text -- Permanent track of human logs, rejection reasons, or why an offer was declined
- `google_form_response_id`: string (Nullable) -- Source response ID used to make form sync idempotent per job
- `form_responses`: jsonb -- Original question titles and answers retained for HR review
- `created_at`: timestamp

The sync operation must explicitly write the final `pipeline_status` and `final_decision` for the screening result before exposing the application: pass maps to `active_pipeline`/`pending`; fail maps to `failed_at_sync`/`fail`.

*Unique Constraints*: A composite index `UNIQUE(candidate_id, job_id)` prevents multi-entry submission clutter on a single role.

CRUD results from the passed/failed dashboard views are validated with a dedicated Pydantic dashboard-record schema, including application, candidate, job title, screening summary, pipeline status, and final decision fields.

Candidate identity lookups query each supplied key. If different keys match different candidate IDs, the operation fails with an ambiguity error and does not merge or modify either profile.

### `interviews`
Tracks sequential tech evaluation segments and links to localized audio paths.
- `id`: uuid (PK)
- `application_id`: uuid (FK -> applications.id)
- `sequence_order`: integer (Round number within the application: Technical Interview 1, 2, etc.; unique per application)
- `scheduled_at`: timestamp (Nullable until HR schedules the round)
- `interview_date`: date (Nullable until the interview takes place; determines the local recording directory)
- `local_audio_path`: string (Nullable until a recording is uploaded) -- Local path pointer using the structural folder naming convention
- `feedback`: text (Nullable) -- Human interviewer notes; no transcript or AI audio analysis is stored
- `status`: enum (pending, complete)

*Unique Constraint*: `UNIQUE(application_id, sequence_order)` prevents duplicate round numbers within one application.

The backend settings read `RECORDINGS_DIR` from the process environment and default to the repository's `backend/recordings` directory. Relative configured paths resolve from the repository root; deployments may provide an absolute mounted-volume path.

Google Forms settings read `GOOGLE_SERVICE_ACCOUNT_FILE` from the environment; relative credential-file paths resolve from the repository root. `GOOGLE_FORM_TEMPLATE_ID` and optional `GOOGLE_DRIVE_FOLDER_ID` identify the Drive template and clone destination. Service accounts need edit access to the template and destination folder, with Drive and Forms API access enabled in the Google Cloud project. Do not commit credential files.

---

## 3. Workflow Implementations & Step-by-Step Logistics

### Phase 1: Target Position Setup & Asset Drafting
1. **Hiring Criteria Processing**: HR inputs role requirements (tech stack, seniority, and required experience) plus optional salary, location, work type, and university details.
2. **JD and Question Drafting**: Gemini Flash API (3.1 Flash-Lite) uses the submitted job criteria to draft the Markdown job description and a dynamic, role-specific set of application questions. HR can review/edit the JD before posting. The question set is structured by type and validated, not chosen from a fixed global question list.
3. **Form Creation**: Google Forms cannot add a file-upload question through Forms API alone. The backend uses Drive to copy a pre-configured template containing the résumé-upload question, updates the copied form's title, and appends the model-generated typed questions plus any missing Full Name, Email Address, Contact Number, and LinkedIn URL questions. The existing résumé question remains in the copied form.
4. **Post and Form Link**: The backend obtains the copied form's responder URL, stores the form ID/URL on the job, and includes that URL in the generated LinkedIn/job post. HR reviews the post before publishing it. The post must link to the newly copied job-specific form, not the template form.

### Phase 2: Per-Job Ingestion, Integrated AI Evaluation, and History Check
1. **The Sync Execution Loop**: HR opens a specific Job Dashboard and clicks "Sync all applicants". The backend retrieves every page of up to 20 responses from that job's linked Google Form, following Google's next-page token, maps each answer to its question title, and processes each response independently. The cloned form includes required name, email, and contact number questions unless the template or generated questions already provide them; LinkedIn URL is optional. Uploaded PDF resumes are downloaded as binary media from Drive and their text is extracted for screening; the backend does not retain a local résumé copy. Original answers remain attached to the application for HR review. A response already stored for the same job is skipped on later syncs.
2. **Identity Verification & Cross-Referencing**:
   - The engine checks incoming records against the global `candidates` data indices (`email`, `phone`, or `linkedin_url`).
   - **Scenario A (New Applicant)**: Initializes a row in `candidates` and maps a fresh entry to `applications`.
   - **Scenario B (Returning Candidate, New Job)**: Detects a global profile match but confirms no entry exists for this new `job_id`. It spins up a new application pointer. The user interface pulls historical sibling applications to show previous job names, stages, statuses, decisions, AI screening summaries, and any human remarks. AI screening summaries and human remarks are displayed separately.
   - **Scenario C (Duplicate Applicant, Same Job)**: Checks email, phone, and LinkedIn URL independently against applicants for the same `job_id`, even when other required form fields are missing. A match on any one field blocks the operation. A PostgreSQL trigger serializes and enforces this rule for concurrent inserts; unique constraints also prevent duplicate `(candidate_id, job_id)` and `(job_id, google_form_response_id)` rows.
3. **The Combined Evaluation Branch**:
   - Programmatic filters replace supplied candidate names, ages, and genders with neutral markers prior to LLM evaluation, preserving unrelated experience text.
   - Gemini Flash API (3.1 Flash) evaluates the candidate's **extracted résumé text AND their textual Google Form responses** simultaneously against the Job Description.
   - **If AI Engine Evaluates as Pass**: `pipeline_status` is marked as `active_pipeline`, and `final_decision` remains `pending`. The candidate moves directly into the standard interview planning interface.
   - **If AI Engine Evaluates as Fail**: `pipeline_status` is flagged as `failed_at_sync` (this is the only AI-failure status enum; never `failed_at_screening`). `final_decision` is set to `fail` because the candidate is not advancing unless HR changes it. The candidate drops out of active processing queues and populates the Failed Candidates filter view.
   - **HR Overrides**: HR can review the failed filter table. If HR manually toggles an applicant to "Pass", `hr_override_status` updates to `pass`, `pipeline_status` transitions to `active_pipeline`, `final_decision` is restored to `pending`, and the `examiner` column updates to the human HR employee's name. This revives the candidate for technical interviews. The CEO remains the only actor who may later lock `final_decision` to `pass` or `fail` after interviews.

### Phase 3: Localized Technical Interview Pipeline
1. **Technical Requirement**: Every passing application track requires at least one core technical interview block, regardless of department context. Video submission challenges are completely deprecated.
2. **HR Applicant Profile Workflow**:
   - HR opens a job and selects or searches for a specific applicant. The job-specific profile shows the AI sync pass/fail result with its explanation and the applicant's interview rounds.
   - Each round appears as a numbered entry (Technical Interview 1, Technical Interview 2, etc.) with its scheduled date, recording verification state, and human feedback.
   - **Schedule New Interview** creates the next pending round for that application, assigning the next `sequence_order` and scheduled date/time. It does not upload or process media.
   - Once at least one interview round exists and all rounds are marked `complete`, HR uses **Move to CEO review** on the Interviews page. The application then leaves the active interview list and becomes available in Executive Review.
3. **Manual Recording Upload**:
   - After the interview, HR opens that specific numbered round and uploads its recording. The upload is associated with the existing interview record, not just the candidate's global profile.
   - The backend validates the interview/application association, sanitizes path segments, saves the file, and verifies the saved file and database path. The directory date is the date the interview took place; the filename includes the round number:
     `./backend/recordings/{job_title}/{candidate_name}/{interview_date_YYYYMMDD}/technical_interview_{sequence_order}.mp3`
   - A round's sequence number is unique within its application, preventing one recording from overwriting another round's file. The database stores `scheduled_at`, `sequence_order`, `local_audio_path`, status, and human feedback.
   - HR may remove any scheduled or completed round from the application. Deletion removes the database row, deletes the associated local recording if present, and reindexes the remaining rounds so `sequence_order` remains contiguous.
4. **Recording Verification**: The UI shows whether the recording exists at its expected local path. Audio contents are not transcribed, chunked, converted, or analyzed by AI.
5. **Jobs Dashboard Overview**: The application includes a portfolio dashboard that lists all jobs as cards with status and lets HR select a job to review the full applicant list. Each job view supports result filters for pass, fail, pending, and search by name/email/application ID.

### Phase 4: Final Executive Determination
1. **Closing Review Hand-off**: Once all technical interview records are marked `complete`, HR moves the candidate to the `ceo_review` tracking phase using the button on the Interviews page. Executive Review is for the CEO's dossier review and final decision.
2. **The CEO Synthesis Dashboard**: Executive Review compiles all data (screening results, verified interview recording paths, human feedback notes, and budget confirmations) into a single summary interface. It does not include generated transcripts or audio analysis.
3. **Ultimate Closure Action**: The CEO reads the file summary and issues the binding pipeline close by clicking either "Approve for Hire" or "Reject Candidate". That dashboard action is the only human write that locks `final_decision` to `pass` or `fail` after interviews. Closing comments or rationale are committed directly to the `remarks` column. (AI screening may have already written `final_decision = fail` with `pipeline_status = failed_at_sync`; that is a system default, not a CEO action, and HR can reverse it as described in Phase 2.)

---

## 4. Prototype REST surface (Streamlit → FastAPI)

All paths are relative to `BACKEND_API_URL` (never hardcoded). JSON unless noted. `GET /health` returns the Pydantic-validated response `{"status":"ok"}` without requiring external credentials or database availability. Feature endpoints are mounted under `/api/v1`.

| Method | Path | Role | Purpose |
|---|---|---|---|
| GET | `/health` | any | Liveness |
| GET | `/api/v1/jobs` | hr, staff | List jobs |
| POST | `/api/v1/jobs` | hr | Create job from hiring criteria |
| POST | `/api/v1/jobs/{job_id}/generate-jd` | hr | Gemini Flash API JD draft into `jd_markdown` |
| PATCH | `/api/v1/jobs/{job_id}` | hr | Save JD edits, status, compensation |
| POST | `/api/v1/jobs/{job_id}/clone-form` | hr | Generate job-specific form questions, clone résumé-upload template, append questions, and persist returned form ID/URL through CRUD |
| POST | `/api/v1/jobs/{job_id}/linkedin-blurb` | hr | Generate reviewed marketing/job post containing the persisted form responder URL |
| POST | `/api/v1/jobs/{job_id}/sync` | hr | Ingest form answers + AI pass/fail |
| GET | `/api/v1/jobs/{job_id}/applications` | hr, staff | Applications for one job (optional `pipeline_status` filter) |
| GET | `/api/v1/candidates/{candidate_id}/history` | hr, staff | Sibling applications with screening summaries and human remarks |
| POST | `/api/v1/applications/{application_id}/hr-override` | hr | Fail pool → `active_pipeline`, `final_decision=pending` |
| POST | `/api/v1/applications/{application_id}/move-to-ceo` | hr | Interviews page hand-off after at least one round exists and all rounds are complete → `ceo_review` |
| GET | `/api/v1/applications/{application_id}/dossier` | staff, hr | CEO synthesis payload |
| POST | `/api/v1/applications/{application_id}/final-decision` | staff (CEO) | Lock `final_decision` pass/fail + remarks |
| GET | `/api/v1/applications/{application_id}/interviews` | hr, staff | Numbered interview rounds for the application, in sequence order |
| POST | `/api/v1/applications/{application_id}/interviews` | hr | Schedule the next numbered interview round |
| DELETE | `/api/v1/interviews/{interview_id}` | hr | Remove a round and reindex remaining interview sequence numbers |
| POST | `/api/v1/interviews/{interview_id}/recording` | hr | Multipart upload for that round → sequence-numbered local recording path |
| PATCH | `/api/v1/interviews/{interview_id}` | hr, staff | Feedback / mark complete |

The sync endpoint takes no applicant payload and returns a `FormSyncResult` with per-response `synced`, `duplicate`, or `error` outcomes. The application list includes candidate name, email, phone, screening summary, and original `form_responses` for the HR result table and selected-applicant detail view. The template's `Contact Number` answer is mapped to the candidate phone field. Candidate history includes both `screening_summary` and `remarks`; the latter is human-authored and is written through the CEO final-decision action, while interview feedback remains attached to interview rounds. The sync results table reports the latest run, while the applicant table reports persisted applications for the selected job. Generated JD and LinkedIn content is shown in its editor immediately after generation. Only response sync requires the `forms.responses.readonly` scope; OAuth users with older tokens are prompted to re-consent when they first run sync. Form cloning continues to use Drive and Forms body scopes.

# Prototype Implementation Plan: DataRopes Recruitment SOP Tool

This plan follows the modular architecture in `project_structure.text` and the lifecycle rules in `spec.md`. Secrets are supplied through environment profiles; `GEMINI_API_KEY` is documented in `.env.example` as a blank template value.

---

## STAGE 1: Core Foundation & Data Modeling — [X] DONE
*Goal: Establish database integrity, validation, and local recording storage.*

### Phase 1.1: Database Schema Migration — [X] DONE
- [X] Create and execute `supabase/migrations/20260928000000_init_recruitment_schema.sql`.
- [X] Establish `candidates`, `jobs`, `applications`, and `interviews` tables.
- [X] Enforce `UNIQUE(candidate_id, job_id)`.
- [X] Enforce `UNIQUE(application_id, sequence_order)` for interview rounds and include `scheduled_at`, actual `interview_date`, and `local_audio_path` on each round.
- [X] Store a concise screening summary on each application for the HR profile; do not store private model reasoning.
- [X] Create `hr_passed_candidates_dashboard` and `hr_failed_candidates_dashboard` views.
- [X] Keep interview records focused on local audio path, human feedback, and verification status; do not add transcript or AI audio-analysis fields.

### Phase 1.2: Pydantic Validation — [X] DONE
- [X] Define job, candidate/application, and interview request/response models in `backend/app/schemas/`.
- [X] Add backend schema dependencies to `backend/requirements.txt` and focused `unittest` coverage in `backend/tests/test_schemas.py`.
- [X] Validate interview scheduling, upload metadata, and local recording verification status; exclude transcript payloads.
- [X] Run `python -m unittest discover -s backend/tests` before marking this phase complete.

### Phase 1.3: Local Media Storage Utilities — [X] DONE
- [X] Read `RECORDINGS_DIR` through global backend settings, defaulting to `./backend/recordings`; resolve relative overrides from the repository root.
- [X] Sanitize job and candidate path segments, prevent traversal, create the required round-numbered path, and never overwrite an existing recording.
- [X] Verify the saved path is a regular, non-empty file; do not parse, transcribe, split, or analyze audio.
- [X] Replace supplied applicant name, age, and gender values with neutral markers before AI screening while preserving unrelated experience text.
- [X] Add focused utility tests in `backend/tests/test_utils.py` and run the backend unittest suite.

---

## STAGE 2: Text-AI Prompts & Provider Integration — [X] DONE
*Goal: Keep prompts and provider-specific code outside routers and core business logic.*

### Phase 2.1: Prompt Definitions — [X] DONE
- [X] Add job-description instructions and a builder using validated `JobCreate` data in `app/prompts/jd_prompts.py`; do not invent criteria.
- [X] Add a screening builder using the JD, anonymized résumé, and form text in `app/prompts/screen_prompts.py`; return only the existing decision and summary contract.
- [X] Treat candidate text as untrusted data; use stated job requirements and evidence only, disclose missing required evidence in the summary, and never request chain-of-thought.
- [X] Add prompt contract tests in `backend/tests/test_prompts.py` and run the full backend unittest suite.
- [X] Do not add interview audio prompts.

### Phase 2.2: Provider-Neutral Service Boundary — [X] DONE
- [X] Define a shared AI provider contract under `app/services/ai/`.
- [X] Implement the prototype adapter with the stable `gemini-3.1-flash-lite` text model; read the selected model from `GEMINI_MODEL`.
- [X] Read the API key from `GEMINI_API_KEY` through global settings and use stateless (`store=False`) requests for applicant data.
- [X] Keep provider selection and SDK details in the services layer so a future OpenAI adapter can be substituted without router or business-logic changes.
- [X] Add `google-genai` to backend dependencies and test the adapter with a fake client; malformed structured output and provider/configuration failures must fail closed.
- [X] Add provider contract tests in `backend/tests/test_ai_provider.py` and rerun the complete unittest suite.

---

## STAGE 3: Database CRUD & External Services
*Goal: Centralize persistence and isolate external integrations.*

### Phase 3.1: CRUD Modules — [X] DONE
- [X] Implement job create/read/list/update, candidate identity/create/history/application lookup, interview schedule/read/update/recording-reference operations, and passed/failed dashboard lookups in `jobs_db.py`, `candidates_db.py`, and `interviews_db.py` under `app/database/crud/`.
- [X] Validate application creation and dashboard rows through Pydantic schemas. Reject ambiguous multi-key candidate matches instead of merging records.
- [X] Add the `supabase` Python dependency and a lazy `app/services/supabase_service.py` bootstrap so CRUD modules can import the client without requiring credentials at module import.
- [X] Read `SUPABASE_URL` and `SUPABASE_SERVICE_ROLE_KEY` through global settings; fail clearly on first database operation if either is missing.
- [X] Keep all database reads, writes, transactions, and view lookups in CRUD modules.
- [X] Add fake-client CRUD tests in `backend/tests/test_crud.py` and run the complete backend unittest suite.

### Phase 3.2: Service Integrations — [X] DONE
- [X] Add a centralized `app/prompts/form_prompts.py` builder that uses validated job criteria to generate a dynamic set of role-specific questions; do not use a fixed question list.
- [X] Add typed Google Form question/result schemas, then implement Drive template copying, title updates, and text/choice question appends in `google_forms.py` using `GOOGLE_SERVICE_ACCOUNT_FILE`, `GOOGLE_FORM_TEMPLATE_ID`, and optional `GOOGLE_DRIVE_FOLDER_ID` from global settings.
- [X] Keep the template's résumé-upload item; return a validated form ID/responder URL for Phase 4 CRUD persistence and job-post linking.
- [X] Wrap local recording storage and verification for an interview record in `local_media_service.py`; keep audio local and do not inspect audio contents.
- [X] Keep Google credentials and local virtual environments out of source control.
- [X] Test question generation and both integrations in `backend/tests/test_services.py` with fake Google API clients and temporary recording directories; do not require credentials or live external calls for unit tests.

---

## STAGE 4: FastAPI Router Layer
*Goal: Keep endpoints thin, schema-validated, and independent of AI vendors.*

### Phase 4.1: Framework Assembly
- Configure `backend/app/main.py`, environment settings, and `backend/app/api/router.py`.
- Ensure API request and response data uses Pydantic schemas.

### Phase 4.2: Feature Endpoints
- Implement job creation, JD generation, edits, form cloning, and LinkedIn copy endpoints.
- Persist cloned form ID/URL through CRUD and ensure the reviewed job post includes that job-specific responder URL.
- Implement candidate sync, identity matching, history, and HR override endpoints.
- Implement interview upload to the required local directory and verify the saved file; do not transcribe or analyze audio.

---

## STAGE 5: Streamlit User Interface
*Goal: Deliver role-aware workflows backed by the FastAPI contract.*

### Phase 5.1: Routing & Session State
- Build `frontend/main.py` with role state for `hr` and `staff`.

### Phase 5.2: Hiring Request UI
- Build hiring criteria inputs, editable JD review, and Google Form setup.

### Phase 5.3: Sync & Screening UI
- Add sync controls, passed/failed application views, applicant history, and HR override actions.

### Phase 5.4: Interview UI
- From a job, let HR search/select an applicant and open the job-specific profile showing sync pass/fail and its explanation.
- List the application's interview rounds by sequence number with schedule, upload/verification state, and human feedback.
- Let HR schedule the next round, then upload a recording to its specific numbered entry; show local-storage verification. Do not display transcripts or automated audio analysis.

### Phase 5.5: Executive Decision UI
- Show screening outcomes, verified recording references, and human feedback; provide the CEO final-decision action.

---

## STAGE 6: Containerization & Local Orchestration
*Goal: Configure reproducible local execution.*

### Phase 6.1: Docker Setup
- Configure backend and frontend Dockerfiles and `docker-compose.yml`.
- Pass `GEMINI_API_KEY` through the environment without committing real credentials.
- Mount the shared recordings directory for backend storage.
# Agents.md - DataRopes Recruitment Tool (Prototype Configuration)

## System Overview
An internal recruitment prototype utilizing a human-in-the-loop architecture. AI acts as an ingestion, cross-referencing, and initial advisory screening engine, while humans retain absolute control over strategic overrides, interview management, and hiring commitments.

## Prototype Role Framework
- **`hr`**: Orchestrates job creation, executes synchronization runs, overrides AI screening failures, and coordinates technical interview audio uploads (video challenges are deprecated).
- **`staff`**: A combined prototype interface executing standard interviewer notes, technical assessments, and the **CEO Final Decision gate**.

## Tech Stack & Environment Architecture
- **Frontend**: Streamlit (Resolves backend API calls via `os.getenv("BACKEND_API_URL")`)
- **Backend**: Python 3.11+, FastAPI (REST API business logic Layer)
- **Database & Storage**: Supabase PostgreSQL for application data and views; interview recordings remain on the local shared volume.
- **Text AI**: Google Gen AI Python SDK for job description generation and applicant screening. Default stable 3.1 text model: `gemini-3.1-flash-lite`; override with `GEMINI_MODEL`. Read credentials through global settings from `GEMINI_API_KEY`.
- **Provider boundary**: Keep AI provider integrations behind a provider-neutral service interface in `backend/app/services/ai/`. Routers and core business logic must not depend on Gemini-specific SDK calls, so an OpenAI adapter can be added later without changing them. Gemini applicant-data requests must disable server-side interaction storage (`store=False`).
- **Interview media**: From a job's applicant list, HR opens or searches for a candidate's job-specific profile, reviews the sync result and its explanation, and sees that application's numbered interview rounds. HR can schedule the next round, then upload its recording from that round's profile entry. `RECORDINGS_DIR` is provided through backend settings (default `./backend/recordings`); path segments are sanitized, saved files are verified, and existing round files are never overwritten. Do not transcribe, slice, or semantically analyze audio in this prototype.

## Documentation Source of Truth
- Folder layout: `project_structure.text` (filename is `.text`, not `.txt`).
- Product workflow and schema: `spec.md`.
- This file: operational constraints, roles, and local run commands.

## Core Architectural Rules & Constraints
1. **Multi-Key Candidate Matching**: Candidates are uniquely identified globally across the platform by a combined lookup of `email`, `phone`, and `linkedin_url`. 
2. **Job-Level Deduplication Constraint**: Candidates are fully permitted to apply to multiple distinct job vacancies over time. However, duplicate entries for the *same job* are strictly blocked. 
3. **Historical Data Assembly**: When an existing candidate profile applies to a new job, the engine hooks their global `candidate_id` and fetches sibling applications to expose previous job names, stages, statuses, decisions, AI screening summaries, and human remarks. Keep AI screening summaries separate from human-authored remarks.
4. **Automated Screening & Failure Cascade**: On synchronization, the AI screening agent outputs an advisory status (`pass` or `fail`).
   - An AI `pass` advances the application directly into the active scheduling pipeline (`pipeline_status = active_pipeline`, `final_decision = pending`).
   - An AI `fail` immediately drops the candidate with `pipeline_status = failed_at_sync` (never `failed_at_screening`) and `final_decision = fail`, because they are not moving forward unless HR changes it.
5. **Human Override Vector**: HR can manually view the failed candidates interface and execute a screening override to change a candidate's status to a `pass`. This sets `hr_override_status = pass`, `pipeline_status = active_pipeline`, restores `final_decision = pending`, and replaces the `examiner` property from `'agent'` to the designated HR human username.
6. **CEO Ultimate Sign-off**: `final_decision` hire/reject after interviews is strictly a CEO dashboard action. System-written `fail` on AI screening (and HR restoring `pending` on override) are the only non-CEO mutations of that column.
7. **Localized Recording Volume**: Each recording belongs to a scheduled interview round for a job application and is stored and verified on disk, without audio processing, as  
   `{RECORDINGS_DIR}/{job_title}/{candidate_name}/{interview_date_YYYYMMDD}/technical_interview_{sequence_order}.mp3` (default root: `./backend/recordings`)
8. **Google Forms Batch Sync**: HR syncs a job's linked form as a batch. Read every response page, map answers by question title, download PDF resumes as binary media from Drive, and extract text for screening. Do not save a local résumé copy. Persist original answers for HR review, map the template's `Contact Number` answer to candidate phone, and anonymize candidate name and email in AI-bound text. Store the response ID to make repeated syncs idempotent, and preserve global identity matching and same-job application uniqueness.
9. **Human Remarks**: `applications.remarks` contains human-authored rationale, not the AI screening summary. The CEO final-decision action writes final remarks; screening summaries remain in `screening_summary` and are displayed separately in candidate history.

## Core Commands
### Container Orchestration
- Build and boot services: `docker-compose up --build`
- Tear down active containers: `docker-compose down`

### Backend Manual Operations
- Start API Engine: `uvicorn app.main:app --reload --host 0.0.0.0 --port 8000`

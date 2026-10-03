-- Fictional local/demo data for the DataRopes recruitment tool.
-- This file contains no credentials and is safe to use in local development.

INSERT INTO public.jobs (
    id,
    title,
    tech_stack,
    seniority,
    required_experience,
    salary,
    location,
    work_type,
    university,
    jd_markdown,
    google_form_id,
    google_form_url,
    linkedin_blurb,
    posted_at,
    closed_at,
    status,
    created_at
)
VALUES
(
    '10000000-0000-0000-0000-000000000001',
    'Senior Data Engineer',
    'Python, PostgreSQL, Airflow, dbt',
    'Senior',
    '5+ years building production data systems',
    '$140,000-$175,000',
    'New York, NY',
    'Hybrid',
    NULL,
    '# Senior Data Engineer\n\nBuild reliable data products with Python, PostgreSQL, Airflow, and dbt.',
    'demo-form-data-engineer',
    'https://docs.google.com/forms/d/demo-form-data-engineer/viewform',
    'We are hiring a Senior Data Engineer. Apply through the job-specific form.',
    '2026-09-28T09:30:00Z',
    NULL,
    'posted',
    '2026-09-28T09:00:00Z'
),
(
    '10000000-0000-0000-0000-000000000002',
    'Product Designer',
    'Figma, user research, design systems',
    'Mid-level',
    '3+ years designing user-centered digital products',
    '$105,000-$135,000',
    'Remote',
    'Remote',
    NULL,
    '# Product Designer\n\nShape clear, accessible workflows for a growing product team.',
    NULL,
    NULL,
    NULL,
    NULL,
    NULL,
    'draft',
    '2026-09-29T09:00:00Z'
),
(
    '10000000-0000-0000-0000-000000000003',
    'Backend Engineer',
    'Python, FastAPI, PostgreSQL, Docker',
    'Mid-level',
    '3+ years building and operating backend services',
    '$120,000-$150,000',
    'Austin, TX',
    'On-site',
    NULL,
    '# Backend Engineer\n\nBuild dependable API services and internal systems.',
    'demo-form-backend-engineer',
    'https://docs.google.com/forms/d/demo-form-backend-engineer/viewform',
    'We are hiring a Backend Engineer in Austin. Apply through the job-specific form.',
    '2026-09-30T09:30:00Z',
    NULL,
    'posted',
    '2026-09-30T09:00:00Z'
)
ON CONFLICT (id) DO UPDATE SET
    title = EXCLUDED.title,
    tech_stack = EXCLUDED.tech_stack,
    seniority = EXCLUDED.seniority,
    required_experience = EXCLUDED.required_experience,
    salary = EXCLUDED.salary,
    location = EXCLUDED.location,
    work_type = EXCLUDED.work_type,
    university = EXCLUDED.university,
    jd_markdown = EXCLUDED.jd_markdown,
    google_form_id = EXCLUDED.google_form_id,
    google_form_url = EXCLUDED.google_form_url,
    linkedin_blurb = EXCLUDED.linkedin_blurb,
    posted_at = EXCLUDED.posted_at,
    closed_at = EXCLUDED.closed_at,
    status = EXCLUDED.status,
    created_at = EXCLUDED.created_at;

INSERT INTO public.candidates (
    id,
    full_name,
    email,
    phone,
    linkedin_url,
    created_at
)
VALUES
(
    '20000000-0000-0000-0000-000000000001',
    'Alex Morgan',
    'alex.morgan.demo@example.com',
    '+1-555-0101',
    'https://www.linkedin.com/in/alex-morgan-demo',
    '2026-09-30T10:00:00Z'
),
(
    '20000000-0000-0000-0000-000000000002',
    'Jordan Lee',
    'jordan.lee.demo@example.com',
    '+1-555-0102',
    'https://www.linkedin.com/in/jordan-lee-demo',
    '2026-09-30T11:00:00Z'
),
(
    '20000000-0000-0000-0000-000000000003',
    'Taylor Kim',
    'taylor.kim.demo@example.com',
    '+1-555-0103',
    'https://www.linkedin.com/in/taylor-kim-demo',
    '2026-10-01T09:00:00Z'
),
(
    '20000000-0000-0000-0000-000000000004',
    'Casey Rivera',
    'casey.rivera.demo@example.com',
    '+1-555-0104',
    'https://www.linkedin.com/in/casey-rivera-demo',
    '2026-10-01T10:00:00Z'
)
ON CONFLICT (id) DO UPDATE SET
    full_name = EXCLUDED.full_name,
    email = EXCLUDED.email,
    phone = EXCLUDED.phone,
    linkedin_url = EXCLUDED.linkedin_url,
    created_at = EXCLUDED.created_at;

INSERT INTO public.applications (
    id,
    candidate_id,
    job_id,
    current_stage,
    agent_decision,
    screening_summary,
    hr_override_status,
    examiner,
    pipeline_status,
    final_decision,
    remarks,
    google_form_response_id,
    form_responses,
    created_at
)
VALUES
(
    '30000000-0000-0000-0000-000000000001',
    '20000000-0000-0000-0000-000000000001',
    '10000000-0000-0000-0000-000000000001',
    'technical_interview',
    'pass',
    'Strong evidence of production Python, PostgreSQL, and orchestration experience.',
    NULL,
    'agent',
    'active_pipeline',
    'pending',
    NULL,
    'demo-response-001',
    '{"Email Address": "alex.morgan.demo@example.com", "Contact Number": "+1-555-0101", "Years of experience": "7 years", "Primary data platform": "Airflow and dbt"}',
    '2026-10-01T12:00:00Z'
),
(
    '30000000-0000-0000-0000-000000000002',
    '20000000-0000-0000-0000-000000000002',
    '10000000-0000-0000-0000-000000000001',
    'sync_evaluation',
    'fail',
    'The submitted evidence does not demonstrate the required production data-platform experience.',
    NULL,
    'agent',
    'failed_at_sync',
    'fail',
    NULL,
    'demo-response-002',
    '{"Email Address": "jordan.lee.demo@example.com", "Contact Number": "+1-555-0102", "Years of experience": "1 year", "Primary data platform": "Course projects"}',
    '2026-10-01T13:00:00Z'
),
(
    '30000000-0000-0000-0000-000000000003',
    '20000000-0000-0000-0000-000000000003',
    '10000000-0000-0000-0000-000000000001',
    'ceo_review',
    'pass',
    'Relevant backend service experience and strong evidence of Python and PostgreSQL delivery.',
    'pass',
    'demo-hr',
    'pending_ceo_decision',
    'pending',
    'HR override applied after reviewing additional experience evidence.',
    'demo-response-003',
    '{"Email Address": "taylor.kim.demo@example.com", "Contact Number": "+1-555-0103", "Years of experience": "5 years", "Additional context": "Built and operated FastAPI services."}',
    '2026-10-01T14:00:00Z'
),
(
    '30000000-0000-0000-0000-000000000004',
    '20000000-0000-0000-0000-000000000004',
    '10000000-0000-0000-0000-000000000003',
    'sync_evaluation',
    'pass',
    'Evidence supports the required Python, FastAPI, and containerized service experience.',
    NULL,
    'agent',
    'active_pipeline',
    'pending',
    NULL,
    'demo-response-004',
    '{"Email Address": "casey.rivera.demo@example.com", "Contact Number": "+1-555-0104", "Years of experience": "4 years", "Deployment experience": "Docker and CI/CD"}',
    '2026-10-02T09:00:00Z'
)
ON CONFLICT (id) DO UPDATE SET
    candidate_id = EXCLUDED.candidate_id,
    job_id = EXCLUDED.job_id,
    current_stage = EXCLUDED.current_stage,
    agent_decision = EXCLUDED.agent_decision,
    screening_summary = EXCLUDED.screening_summary,
    hr_override_status = EXCLUDED.hr_override_status,
    examiner = EXCLUDED.examiner,
    pipeline_status = EXCLUDED.pipeline_status,
    final_decision = EXCLUDED.final_decision,
    remarks = EXCLUDED.remarks,
    google_form_response_id = EXCLUDED.google_form_response_id,
    form_responses = EXCLUDED.form_responses,
    created_at = EXCLUDED.created_at;

INSERT INTO public.interviews (
    id,
    application_id,
    sequence_order,
    scheduled_at,
    interview_date,
    local_audio_path,
    feedback,
    status,
    created_at
)
VALUES
(
    '40000000-0000-0000-0000-000000000001',
    '30000000-0000-0000-0000-000000000001',
    1,
    '2026-10-05T15:00:00Z',
    NULL,
    NULL,
    NULL,
    'pending',
    '2026-10-02T10:00:00Z'
),
(
    '40000000-0000-0000-0000-000000000002',
    '30000000-0000-0000-0000-000000000003',
    1,
    '2026-10-02T15:00:00Z',
    '2026-10-02',
    'backend/recordings/Backend_Engineer/Taylor_Kim/20261002/technical_interview_1.mp3',
    'Clear explanation of API boundaries, validation, and failure handling.',
    'complete',
    '2026-10-01T10:00:00Z'
),
(
    '40000000-0000-0000-0000-000000000003',
    '30000000-0000-0000-0000-000000000003',
    2,
    '2026-10-06T15:00:00Z',
    '2026-10-06',
    'backend/recordings/Backend_Engineer/Taylor_Kim/20261006/technical_interview_2.mp3',
    'Strong systems thinking and practical tradeoff discussion.',
    'complete',
    '2026-10-02T10:30:00Z'
)
ON CONFLICT (id) DO UPDATE SET
    application_id = EXCLUDED.application_id,
    sequence_order = EXCLUDED.sequence_order,
    scheduled_at = EXCLUDED.scheduled_at,
    interview_date = EXCLUDED.interview_date,
    local_audio_path = EXCLUDED.local_audio_path,
    feedback = EXCLUDED.feedback,
    status = EXCLUDED.status,
    created_at = EXCLUDED.created_at;

INSERT INTO public.jobs (
    id,
    title,
    tech_stack,
    seniority,
    required_experience,
    salary,
    location,
    work_type,
    university,
    jd_markdown,
    google_form_id,
    google_form_url,
    linkedin_blurb,
    posted_at,
    closed_at,
    status,
    created_at
)
VALUES (
    '10000000-0000-0000-0000-000000000004',
    'QA Automation Engineer',
    'Python, Playwright, CI/CD',
    'Mid-level',
    '3+ years building automated test suites',
    '$110,000-$140,000',
    'Chicago, IL',
    'Hybrid',
    NULL,
    '# QA Automation Engineer\n\nBuild reliable automated quality systems.',
    NULL,
    NULL,
    NULL,
    '2026-09-15T09:00:00Z',
    '2026-09-30T17:00:00Z',
    'closed',
    '2026-09-15T08:30:00Z'
)
ON CONFLICT (id) DO UPDATE SET
    title = EXCLUDED.title,
    tech_stack = EXCLUDED.tech_stack,
    seniority = EXCLUDED.seniority,
    required_experience = EXCLUDED.required_experience,
    salary = EXCLUDED.salary,
    location = EXCLUDED.location,
    work_type = EXCLUDED.work_type,
    university = EXCLUDED.university,
    jd_markdown = EXCLUDED.jd_markdown,
    google_form_id = EXCLUDED.google_form_id,
    google_form_url = EXCLUDED.google_form_url,
    linkedin_blurb = EXCLUDED.linkedin_blurb,
    posted_at = EXCLUDED.posted_at,
    closed_at = EXCLUDED.closed_at,
    status = EXCLUDED.status,
    created_at = EXCLUDED.created_at;

INSERT INTO public.candidates (
    id,
    full_name,
    email,
    phone,
    linkedin_url,
    created_at
)
VALUES
(
    '20000000-0000-0000-0000-000000000005',
    'Morgan Patel',
    'morgan.patel.demo@example.com',
    '+1-555-0105',
    'https://www.linkedin.com/in/morgan-patel-demo',
    '2026-09-20T10:00:00Z'
),
(
    '20000000-0000-0000-0000-000000000006',
    'Riley Chen',
    'riley.chen.demo@example.com',
    '+1-555-0106',
    'https://www.linkedin.com/in/riley-chen-demo',
    '2026-09-20T11:00:00Z'
)
ON CONFLICT (id) DO UPDATE SET
    full_name = EXCLUDED.full_name,
    email = EXCLUDED.email,
    phone = EXCLUDED.phone,
    linkedin_url = EXCLUDED.linkedin_url,
    created_at = EXCLUDED.created_at;

UPDATE public.applications
SET current_stage = 'technical_interview'
WHERE id = '30000000-0000-0000-0000-000000000004';

INSERT INTO public.applications (
    id,
    candidate_id,
    job_id,
    current_stage,
    agent_decision,
    screening_summary,
    hr_override_status,
    examiner,
    pipeline_status,
    final_decision,
    remarks,
    google_form_response_id,
    form_responses,
    created_at
)
VALUES
(
    '30000000-0000-0000-0000-000000000005',
    '20000000-0000-0000-0000-000000000005',
    '10000000-0000-0000-0000-000000000004',
    'closed',
    'pass',
    'Strong automation experience and clear evidence of Playwright delivery.',
    NULL,
    'agent',
    'closed_complete',
    'pass',
    'Hired after completing the interview process.',
    'demo-response-005',
    '{"Email Address": "morgan.patel.demo@example.com", "Contact Number": "+1-555-0105", "Automation experience": "5 years", "Primary framework": "Playwright"}',
    '2026-09-21T12:00:00Z'
),
(
    '30000000-0000-0000-0000-000000000006',
    '20000000-0000-0000-0000-000000000006',
    '10000000-0000-0000-0000-000000000004',
    'closed',
    'pass',
    'The candidate passed sync screening but did not meet the final technical bar.',
    NULL,
    'agent',
    'closed_complete',
    'fail',
    'Rejected by CEO after final interview review.',
    'demo-response-006',
    '{"Email Address": "riley.chen.demo@example.com", "Contact Number": "+1-555-0106", "Automation experience": "3 years", "Primary framework": "Selenium"}',
    '2026-09-21T13:00:00Z'
)
ON CONFLICT (id) DO UPDATE SET
    candidate_id = EXCLUDED.candidate_id,
    job_id = EXCLUDED.job_id,
    current_stage = EXCLUDED.current_stage,
    agent_decision = EXCLUDED.agent_decision,
    screening_summary = EXCLUDED.screening_summary,
    hr_override_status = EXCLUDED.hr_override_status,
    examiner = EXCLUDED.examiner,
    pipeline_status = EXCLUDED.pipeline_status,
    final_decision = EXCLUDED.final_decision,
    remarks = EXCLUDED.remarks,
    google_form_response_id = EXCLUDED.google_form_response_id,
    form_responses = EXCLUDED.form_responses,
    created_at = EXCLUDED.created_at;

INSERT INTO public.interviews (
    id,
    application_id,
    sequence_order,
    scheduled_at,
    interview_date,
    local_audio_path,
    feedback,
    status,
    created_at
)
VALUES
(
    '40000000-0000-0000-0000-000000000004',
    '30000000-0000-0000-0000-000000000004',
    1,
    '2026-10-03T15:00:00Z',
    '2026-10-03',
    'backend/recordings/Backend_Engineer/Casey_Rivera/20261003/technical_interview_1.mp3',
    'Completed first technical interview.',
    'complete',
    '2026-10-02T11:00:00Z'
),
(
    '40000000-0000-0000-0000-000000000005',
    '30000000-0000-0000-0000-000000000004',
    2,
    '2026-10-08T15:00:00Z',
    NULL,
    NULL,
    NULL,
    'pending',
    '2026-10-02T11:30:00Z'
)
ON CONFLICT (id) DO UPDATE SET
    application_id = EXCLUDED.application_id,
    sequence_order = EXCLUDED.sequence_order,
    scheduled_at = EXCLUDED.scheduled_at,
    interview_date = EXCLUDED.interview_date,
    local_audio_path = EXCLUDED.local_audio_path,
    feedback = EXCLUDED.feedback,
    status = EXCLUDED.status,
    created_at = EXCLUDED.created_at;

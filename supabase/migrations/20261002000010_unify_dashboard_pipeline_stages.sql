CREATE OR REPLACE FUNCTION public.dashboard_application_matches_stage(
    p_application_id uuid,
    p_stage text
)
RETURNS boolean
LANGUAGE sql
STABLE
SECURITY INVOKER
SET search_path = public
AS $$
    SELECT CASE p_stage
        WHEN 'stage_one' THEN EXISTS (
            SELECT 1
            FROM public.applications AS application
            WHERE application.id = p_application_id
              AND application.pipeline_status = 'active_pipeline'::public.pipeline_status
              AND (
                  application.agent_decision = 'pass'::public.screening_decision
                  OR application.hr_override_status = 'pass'::public.screening_decision
              )
              AND NOT EXISTS (
                  SELECT 1
                  FROM public.interviews AS interview
                  WHERE interview.application_id = application.id
                    AND interview.scheduled_at IS NOT NULL
              )
        )
        WHEN 'first_interview_scheduled' THEN EXISTS (
            SELECT 1
            FROM public.applications AS application
            JOIN public.interviews AS first_round
                ON first_round.application_id = application.id
               AND first_round.sequence_order = 1
            WHERE application.id = p_application_id
              AND application.pipeline_status = 'active_pipeline'::public.pipeline_status
              AND first_round.scheduled_at IS NOT NULL
              AND first_round.status = 'pending'::public.interview_status
        )
        WHEN 'second_interview' THEN EXISTS (
            SELECT 1
            FROM public.applications AS application
            JOIN public.interviews AS first_round
                ON first_round.application_id = application.id
               AND first_round.sequence_order = 1
            JOIN public.interviews AS second_round
                ON second_round.application_id = application.id
               AND second_round.sequence_order = 2
            WHERE application.id = p_application_id
              AND application.pipeline_status = 'active_pipeline'::public.pipeline_status
              AND first_round.status = 'complete'::public.interview_status
              AND second_round.scheduled_at IS NOT NULL
              AND second_round.status = 'pending'::public.interview_status
        )
        WHEN 'ceo_review' THEN EXISTS (
            SELECT 1
            FROM public.applications AS application
            WHERE application.id = p_application_id
              AND application.pipeline_status = 'pending_ceo_decision'::public.pipeline_status
              AND EXISTS (
                  SELECT 1
                  FROM public.interviews AS interview
                  WHERE interview.application_id = application.id
              )
              AND NOT EXISTS (
                  SELECT 1
                  FROM public.interviews AS interview
                  WHERE interview.application_id = application.id
                    AND interview.status <> 'complete'::public.interview_status
              )
        )
        ELSE false
    END;
$$;

REVOKE ALL ON FUNCTION public.dashboard_application_matches_stage(uuid, text)
    FROM PUBLIC, anon, authenticated;
GRANT EXECUTE ON FUNCTION public.dashboard_application_matches_stage(uuid, text)
    TO service_role;

DROP FUNCTION public.get_command_center_summary();

CREATE FUNCTION public.get_command_center_summary()
RETURNS TABLE (
    jobs jsonb,
    draft_job_count bigint,
    posted_job_count bigint,
    total_job_count bigint,
    open_job_count bigint,
    closed_job_count bigint,
    application_count bigint,
    active_pipeline_count bigint,
    ceo_decision_count bigint,
    stage1_pass_count bigint,
    first_interview_scheduled_count bigint,
    second_interview_count bigint,
    successful_applicant_count bigint,
    ceo_failed_applicant_count bigint
)
LANGUAGE sql
STABLE
SECURITY INVOKER
SET search_path = public
AS $$
    WITH job_rollups AS (
        SELECT
            job.*,
            count(application.id) AS application_count,
            count(application.id) FILTER (
                WHERE public.dashboard_application_matches_stage(application.id, 'stage_one')
            ) AS stage1_pass_count,
            count(application.id) FILTER (
                WHERE public.dashboard_application_matches_stage(application.id, 'first_interview_scheduled')
            ) AS first_interview_scheduled_count,
            count(application.id) FILTER (
                WHERE public.dashboard_application_matches_stage(application.id, 'second_interview')
            ) AS second_interview_count,
            count(application.id) FILTER (
                WHERE public.dashboard_application_matches_stage(application.id, 'ceo_review')
            ) AS ceo_decision_count,
            count(application.id) FILTER (
                WHERE application.final_decision = 'pass'::public.final_decision
            ) AS successful_applicant_count,
            count(application.id) FILTER (
                WHERE application.final_decision = 'fail'::public.final_decision
                  AND application.pipeline_status = 'closed_complete'::public.pipeline_status
            ) AS ceo_failed_applicant_count
        FROM public.jobs AS job
        LEFT JOIN public.applications AS application
            ON application.job_id = job.id
        GROUP BY job.id
    ),
    job_counts AS (
        SELECT
            count(*) FILTER (WHERE status = 'draft'::public.job_status) AS draft_job_count,
            count(*) FILTER (WHERE status = 'posted'::public.job_status) AS posted_job_count,
            count(*) AS total_job_count,
            count(*) FILTER (WHERE status = 'posted'::public.job_status) AS open_job_count,
            count(*) FILTER (WHERE status = 'closed'::public.job_status) AS closed_job_count
        FROM public.jobs
    ),
    application_counts AS (
        SELECT
            count(*) AS application_count,
            count(*) FILTER (
                WHERE application.pipeline_status = 'active_pipeline'::public.pipeline_status
            ) AS active_pipeline_count,
            count(*) FILTER (
                WHERE public.dashboard_application_matches_stage(application.id, 'ceo_review')
            ) AS ceo_decision_count,
            count(*) FILTER (
                WHERE public.dashboard_application_matches_stage(application.id, 'stage_one')
            ) AS stage1_pass_count,
            count(*) FILTER (
                WHERE public.dashboard_application_matches_stage(application.id, 'first_interview_scheduled')
            ) AS first_interview_scheduled_count,
            count(*) FILTER (
                WHERE public.dashboard_application_matches_stage(application.id, 'second_interview')
            ) AS second_interview_count,
            count(*) FILTER (
                WHERE application.final_decision = 'pass'::public.final_decision
            ) AS successful_applicant_count,
            count(*) FILTER (
                WHERE application.final_decision = 'fail'::public.final_decision
                  AND application.pipeline_status = 'closed_complete'::public.pipeline_status
            ) AS ceo_failed_applicant_count
        FROM public.applications AS application
    )
    SELECT
        COALESCE(
            (
                SELECT jsonb_agg(
                    to_jsonb(job_rollup)
                    ORDER BY job_rollup.created_at DESC
                )
                FROM job_rollups AS job_rollup
            ),
            '[]'::jsonb
        ),
        job_counts.draft_job_count,
        job_counts.posted_job_count,
        job_counts.total_job_count,
        job_counts.open_job_count,
        job_counts.closed_job_count,
        application_counts.application_count,
        application_counts.active_pipeline_count,
        application_counts.ceo_decision_count,
        application_counts.stage1_pass_count,
        application_counts.first_interview_scheduled_count,
        application_counts.second_interview_count,
        application_counts.successful_applicant_count,
        application_counts.ceo_failed_applicant_count
    FROM job_counts
    CROSS JOIN application_counts;
$$;

REVOKE ALL ON FUNCTION public.get_command_center_summary()
    FROM PUBLIC, anon, authenticated;
GRANT EXECUTE ON FUNCTION public.get_command_center_summary()
    TO service_role;

DROP FUNCTION public.get_job_dashboard_page(uuid, text, text, integer, integer, uuid);

CREATE FUNCTION public.get_job_dashboard_page(
    p_job_id uuid,
    p_decision_filter text DEFAULT 'all',
    p_search text DEFAULT NULL,
    p_offset integer DEFAULT 0,
    p_limit integer DEFAULT 20,
    p_selected_application_id uuid DEFAULT NULL
)
RETURNS TABLE (
    job_exists boolean,
    total_count bigint,
    applicants jsonb,
    selected_application jsonb
)
LANGUAGE sql
STABLE
SECURITY INVOKER
SET search_path = public
AS $$
    WITH matches AS MATERIALIZED (
        SELECT
            application.id AS application_id,
            application.created_at,
            candidate.full_name AS candidate_name,
            candidate.email,
            candidate.phone,
            application.agent_decision,
            application.pipeline_status,
            application.final_decision,
            application.screening_summary
        FROM public.applications AS application
        JOIN public.candidates AS candidate
            ON candidate.id = application.candidate_id
        WHERE application.job_id = p_job_id
          AND (
              p_decision_filter = 'all'
              OR (
                  p_decision_filter = 'pass'
                  AND application.agent_decision = 'pass'::public.screening_decision
              )
              OR (
                  p_decision_filter = 'fail'
                  AND application.agent_decision = 'fail'::public.screening_decision
              )
              OR (
                  p_decision_filter = 'pending'
                  AND (
                      application.agent_decision IS NULL
                      OR application.final_decision = 'pending'::public.final_decision
                  )
              )
              OR public.dashboard_application_matches_stage(application.id, p_decision_filter)
          )
          AND (
              NULLIF(btrim(p_search), '') IS NULL
              OR candidate.full_name ILIKE '%' || btrim(p_search) || '%'
              OR candidate.email ILIKE '%' || btrim(p_search) || '%'
              OR application.id::text ILIKE '%' || btrim(p_search) || '%'
          )
    ),
    page_ids AS MATERIALIZED (
        SELECT application_id, created_at
        FROM matches
        ORDER BY created_at DESC, application_id DESC
        OFFSET GREATEST(p_offset, 0)
        LIMIT LEAST(GREATEST(p_limit, 1), 100)
    ),
    selected_id AS (
        SELECT COALESCE(
            (
                SELECT application_id
                FROM page_ids
                WHERE application_id = p_selected_application_id
            ),
            (
                SELECT application_id
                FROM page_ids
                ORDER BY created_at DESC, application_id DESC
                LIMIT 1
            )
        ) AS application_id
    )
    SELECT
        EXISTS (SELECT 1 FROM public.jobs WHERE id = p_job_id),
        (SELECT count(*) FROM matches),
        COALESCE(
            (
                SELECT jsonb_agg(
                    jsonb_build_object(
                        'id', matches.application_id,
                        'candidate_name', matches.candidate_name,
                        'email', matches.email,
                        'phone', matches.phone,
                        'agent_decision', matches.agent_decision,
                        'pipeline_status', matches.pipeline_status,
                        'final_decision', matches.final_decision,
                        'screening_summary', matches.screening_summary
                    )
                    ORDER BY page_ids.created_at DESC, page_ids.application_id DESC
                )
                FROM page_ids
                JOIN matches USING (application_id, created_at)
            ),
            '[]'::jsonb
        ),
        (
            SELECT to_jsonb(application)
            FROM selected_id
            JOIN public.applications AS application
                ON application.id = selected_id.application_id
        );
$$;

REVOKE ALL ON FUNCTION public.get_job_dashboard_page(uuid, text, text, integer, integer, uuid)
    FROM PUBLIC, anon, authenticated;
GRANT EXECUTE ON FUNCTION public.get_job_dashboard_page(uuid, text, text, integer, integer, uuid)
    TO service_role;

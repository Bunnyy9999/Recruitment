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
    WITH job_counts AS (
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
                WHERE application.pipeline_status = 'pending_ceo_decision'::public.pipeline_status
            ) AS ceo_decision_count,
            count(*) FILTER (
                WHERE application.agent_decision = 'pass'::public.screening_decision
                   OR application.hr_override_status = 'pass'::public.screening_decision
            ) AS stage1_pass_count,
            count(*) FILTER (
                WHERE EXISTS (
                    SELECT 1
                    FROM public.interviews AS first_round
                    WHERE first_round.application_id = application.id
                      AND first_round.sequence_order = 1
                      AND first_round.status = 'pending'::public.interview_status
                      AND first_round.scheduled_at IS NOT NULL
                )
            ) AS first_interview_scheduled_count,
            count(*) FILTER (
                WHERE application.pipeline_status = 'active_pipeline'::public.pipeline_status
                  AND EXISTS (
                      SELECT 1
                      FROM public.interviews AS first_round
                      WHERE first_round.application_id = application.id
                        AND first_round.sequence_order = 1
                        AND first_round.status = 'complete'::public.interview_status
                  )
                  AND EXISTS (
                      SELECT 1
                      FROM public.interviews AS second_round
                      WHERE second_round.application_id = application.id
                        AND second_round.sequence_order = 2
                        AND second_round.status = 'pending'::public.interview_status
                  )
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
                SELECT jsonb_agg(to_jsonb(job) ORDER BY job.created_at DESC)
                FROM public.jobs AS job
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

REVOKE ALL ON FUNCTION public.get_command_center_summary() FROM PUBLIC, anon, authenticated;
GRANT EXECUTE ON FUNCTION public.get_command_center_summary() TO service_role;
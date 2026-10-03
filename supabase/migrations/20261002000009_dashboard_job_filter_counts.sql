ALTER TABLE public.jobs
    ADD COLUMN posted_at timestamptz,
    ADD COLUMN closed_at timestamptz;

UPDATE public.jobs
SET posted_at = created_at
WHERE status IN ('posted'::public.job_status, 'closed'::public.job_status)
  AND posted_at IS NULL;

UPDATE public.jobs
SET closed_at = created_at
WHERE status = 'closed'::public.job_status
    AND closed_at IS NULL;

CREATE OR REPLACE FUNCTION public.set_job_posted_at()
RETURNS trigger
LANGUAGE plpgsql
AS $$
BEGIN
    IF NEW.status = 'posted'::public.job_status
       AND (TG_OP = 'INSERT' OR OLD.status IS DISTINCT FROM 'posted'::public.job_status)
       AND NEW.posted_at IS NULL THEN
        NEW.posted_at = now();
    END IF;
    IF NEW.status = 'closed'::public.job_status
       AND (TG_OP = 'INSERT' OR OLD.status IS DISTINCT FROM 'closed'::public.job_status)
       AND NEW.closed_at IS NULL THEN
        NEW.closed_at = now();
    END IF;
    RETURN NEW;
END;
$$;

CREATE TRIGGER jobs_set_posted_at
    BEFORE INSERT OR UPDATE OF status
    ON public.jobs
    FOR EACH ROW
    EXECUTE FUNCTION public.set_job_posted_at();

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
                WHERE application.agent_decision = 'pass'::public.screening_decision
                   OR application.hr_override_status = 'pass'::public.screening_decision
            ) AS stage1_pass_count,
            count(application.id) FILTER (
                WHERE EXISTS (
                    SELECT 1
                    FROM public.interviews AS first_round
                    WHERE first_round.application_id = application.id
                      AND first_round.sequence_order = 1
                      AND first_round.status = 'pending'::public.interview_status
                      AND first_round.scheduled_at IS NOT NULL
                )
            ) AS first_interview_scheduled_count,
            count(application.id) FILTER (
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
            count(application.id) FILTER (
                WHERE application.pipeline_status = 'pending_ceo_decision'::public.pipeline_status
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

REVOKE ALL ON FUNCTION public.get_command_center_summary() FROM PUBLIC, anon, authenticated;
GRANT EXECUTE ON FUNCTION public.get_command_center_summary() TO service_role;

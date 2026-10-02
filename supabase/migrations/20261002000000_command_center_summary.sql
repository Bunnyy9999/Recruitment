CREATE OR REPLACE FUNCTION public.get_command_center_summary()
RETURNS TABLE (
    jobs jsonb,
    application_count bigint,
    active_pipeline_count bigint,
    ceo_decision_count bigint
)
LANGUAGE sql
STABLE
SECURITY INVOKER
SET search_path = public
AS $$
    WITH application_counts AS (
        SELECT
            count(*) AS application_count,
            count(*) FILTER (
                WHERE pipeline_status = 'active_pipeline'::public.pipeline_status
            ) AS active_pipeline_count,
            count(*) FILTER (
                WHERE pipeline_status = 'pending_ceo_decision'::public.pipeline_status
            ) AS ceo_decision_count
        FROM public.applications
    )
    SELECT
        COALESCE(
            (
                SELECT jsonb_agg(to_jsonb(job) ORDER BY job.created_at DESC)
                FROM public.jobs AS job
            ),
            '[]'::jsonb
        ),
        application_counts.application_count,
        application_counts.active_pipeline_count,
        application_counts.ceo_decision_count
    FROM application_counts;
$$;

REVOKE ALL ON FUNCTION public.get_command_center_summary() FROM PUBLIC, anon, authenticated;
GRANT EXECUTE ON FUNCTION public.get_command_center_summary() TO service_role;
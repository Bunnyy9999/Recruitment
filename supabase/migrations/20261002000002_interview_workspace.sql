CREATE OR REPLACE FUNCTION public.get_interview_workspace(
    p_job_id uuid,
    p_application_id uuid DEFAULT NULL
)
RETURNS TABLE (
    job_exists boolean,
    selected_application_exists boolean,
    applicants jsonb,
    rounds jsonb
)
LANGUAGE sql
STABLE
SECURITY INVOKER
SET search_path = public
AS $$
    SELECT
        EXISTS (
            SELECT 1 FROM public.jobs WHERE id = p_job_id
        ),
        p_application_id IS NULL OR EXISTS (
            SELECT 1
            FROM public.applications AS application
            WHERE application.id = p_application_id
              AND application.job_id = p_job_id
              AND application.pipeline_status = 'active_pipeline'::public.pipeline_status
        ),
        COALESCE(
            (
                SELECT jsonb_agg(
                    jsonb_build_object(
                        'id', application.id,
                        'candidate_name', candidate.full_name,
                        'email', candidate.email,
                        'pipeline_status', application.pipeline_status
                    )
                    ORDER BY application.created_at DESC, application.id DESC
                )
                FROM public.applications AS application
                JOIN public.candidates AS candidate
                    ON candidate.id = application.candidate_id
                WHERE application.job_id = p_job_id
                  AND application.pipeline_status = 'active_pipeline'::public.pipeline_status
            ),
            '[]'::jsonb
        ),
        COALESCE(
            (
                SELECT jsonb_agg(to_jsonb(interview) ORDER BY interview.sequence_order)
                FROM public.interviews AS interview
                WHERE interview.application_id = p_application_id
                  AND EXISTS (
                      SELECT 1
                      FROM public.applications AS application
                      WHERE application.id = p_application_id
                        AND application.job_id = p_job_id
                        AND application.pipeline_status = 'active_pipeline'::public.pipeline_status
                  )
            ),
            '[]'::jsonb
        );
$$;

REVOKE ALL ON FUNCTION public.get_interview_workspace(uuid, uuid)
    FROM PUBLIC, anon, authenticated;
GRANT EXECUTE ON FUNCTION public.get_interview_workspace(uuid, uuid)
    TO service_role;
CREATE OR REPLACE FUNCTION public.get_executive_workspace(
    p_job_id uuid,
    p_application_id uuid DEFAULT NULL
)
RETURNS TABLE (
    job_exists boolean,
    selected_application_exists boolean,
    eligible_applicants jsonb,
    dossier jsonb
)
LANGUAGE sql
STABLE
SECURITY INVOKER
SET search_path = public
AS $$
    WITH eligible AS MATERIALIZED (
        SELECT
            application.id AS application_id,
            application.pipeline_status,
            application.created_at,
            candidate.full_name AS candidate_name,
            candidate.email
        FROM public.applications AS application
        JOIN public.candidates AS candidate
            ON candidate.id = application.candidate_id
        WHERE application.job_id = p_job_id
          AND application.pipeline_status IN (
              'active_pipeline'::public.pipeline_status,
              'pending_ceo_decision'::public.pipeline_status
          )
    )
    SELECT
        EXISTS (
            SELECT 1 FROM public.jobs WHERE id = p_job_id
        ),
        p_application_id IS NULL OR EXISTS (
            SELECT 1 FROM eligible WHERE application_id = p_application_id
        ),
        COALESCE(
            (
                SELECT jsonb_agg(
                    jsonb_build_object(
                        'id', application_id,
                        'candidate_name', candidate_name,
                        'email', email,
                        'pipeline_status', pipeline_status
                    )
                    ORDER BY created_at DESC, application_id DESC
                )
                FROM eligible
            ),
            '[]'::jsonb
        ),
        (
            SELECT jsonb_build_object(
                'application', to_jsonb(application),
                'interviews', COALESCE(
                    (
                        SELECT jsonb_agg(to_jsonb(interview) ORDER BY interview.sequence_order)
                        FROM public.interviews AS interview
                        WHERE interview.application_id = application.id
                    ),
                    '[]'::jsonb
                )
            )
            FROM public.applications AS application
            WHERE application.id = p_application_id
              AND application.job_id = p_job_id
              AND application.pipeline_status IN (
                  'active_pipeline'::public.pipeline_status,
                  'pending_ceo_decision'::public.pipeline_status
              )
        );
$$;

REVOKE ALL ON FUNCTION public.get_executive_workspace(uuid, uuid)
    FROM PUBLIC, anon, authenticated;
GRANT EXECUTE ON FUNCTION public.get_executive_workspace(uuid, uuid)
    TO service_role;
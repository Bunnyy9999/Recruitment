CREATE OR REPLACE FUNCTION public.get_job_dashboard_page(
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
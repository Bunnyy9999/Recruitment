CREATE OR REPLACE FUNCTION public.list_job_applicants_page(
    p_job_id uuid,
    p_agent_decision text DEFAULT NULL,
    p_has_other_applications boolean DEFAULT NULL,
    p_search text DEFAULT NULL,
    p_offset integer DEFAULT 0,
    p_limit integer DEFAULT 20
)
RETURNS TABLE (
    job_exists boolean,
    total_count bigint,
    applicants jsonb
)
LANGUAGE sql
STABLE
SECURITY INVOKER
SET search_path = public
AS $$
    WITH eligible AS MATERIALIZED (
        SELECT
            application.id AS application_id,
            application.candidate_id,
            application.job_id,
            application.created_at,
            candidate.full_name AS candidate_name,
            candidate.email,
            candidate.phone
        FROM public.applications AS application
        JOIN public.candidates AS candidate
            ON candidate.id = application.candidate_id
        WHERE application.job_id = p_job_id
          AND (
              p_agent_decision IS NULL
              OR application.agent_decision::text = p_agent_decision
          )
          AND (
              NULLIF(btrim(p_search), '') IS NULL
              OR candidate.full_name ILIKE '%' || btrim(p_search) || '%'
              OR candidate.email ILIKE '%' || btrim(p_search) || '%'
              OR application.id::text ILIKE '%' || btrim(p_search) || '%'
          )
    ),
    matches AS MATERIALIZED (
        SELECT
            eligible.*,
            EXISTS (
                SELECT 1
                FROM public.applications AS other_application
                WHERE other_application.candidate_id = eligible.candidate_id
                  AND other_application.job_id <> eligible.job_id
            ) AS has_other_applications
        FROM eligible
    ),
    filtered_matches AS MATERIALIZED (
        SELECT *
        FROM matches
        WHERE p_has_other_applications IS NULL
           OR has_other_applications = p_has_other_applications
    ),
    page_ids AS MATERIALIZED (
        SELECT application_id, created_at
        FROM filtered_matches
        ORDER BY created_at DESC, application_id DESC
        OFFSET GREATEST(p_offset, 0)
        LIMIT LEAST(GREATEST(p_limit, 1), 100)
    ),
    page AS (
        SELECT
            to_jsonb(application) || jsonb_build_object(
                'candidate_name', filtered_matches.candidate_name,
                'email', filtered_matches.email,
                'phone', filtered_matches.phone,
                'has_other_applications', filtered_matches.has_other_applications
            ) AS item,
            page_ids.created_at,
            page_ids.application_id
        FROM page_ids
        JOIN filtered_matches USING (application_id, created_at)
        JOIN public.applications AS application
            ON application.id = page_ids.application_id
    )
    SELECT
        EXISTS (SELECT 1 FROM public.jobs WHERE id = p_job_id),
        (SELECT count(*) FROM filtered_matches),
        COALESCE(
            (SELECT jsonb_agg(item ORDER BY created_at DESC, application_id DESC) FROM page),
            '[]'::jsonb
        );
$$;

REVOKE ALL ON FUNCTION public.list_job_applicants_page(uuid, text, boolean, text, integer, integer)
    FROM PUBLIC, anon, authenticated;
GRANT EXECUTE ON FUNCTION public.list_job_applicants_page(uuid, text, boolean, text, integer, integer)
    TO service_role;
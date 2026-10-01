ALTER TABLE public.jobs
    ADD COLUMN salary text,
    ADD COLUMN location text,
    ADD COLUMN work_type text,
    ADD COLUMN required_experience text NOT NULL DEFAULT 'Not specified',
    ADD COLUMN university text;

UPDATE public.jobs
SET salary = CASE
    WHEN compensation_min IS NOT NULL AND compensation_max IS NOT NULL
        THEN compensation_min::text || ' - ' || compensation_max::text
    ELSE COALESCE(compensation_min::text, compensation_max::text)
END;

ALTER TABLE public.jobs
    DROP CONSTRAINT jobs_compensation_min_nonnegative,
    DROP CONSTRAINT jobs_compensation_max_nonnegative,
    DROP CONSTRAINT jobs_compensation_range_valid,
    ALTER COLUMN required_experience DROP DEFAULT,
    DROP COLUMN compensation_min,
    DROP COLUMN compensation_max;

CREATE OR REPLACE FUNCTION public.reject_duplicate_job_applicant_identity()
RETURNS trigger
LANGUAGE plpgsql
AS $$
DECLARE
    candidate_email text;
    candidate_phone text;
    candidate_linkedin text;
BEGIN
    PERFORM pg_advisory_xact_lock(hashtextextended(NEW.job_id::text, 0));

    SELECT email, phone, linkedin_url
    INTO candidate_email, candidate_phone, candidate_linkedin
    FROM public.candidates
    WHERE id = NEW.candidate_id;

    IF NOT FOUND THEN
        RETURN NEW;
    END IF;

    IF EXISTS (
        SELECT 1
        FROM public.applications AS existing_application
        JOIN public.candidates AS existing_candidate
            ON existing_candidate.id = existing_application.candidate_id
        WHERE existing_application.job_id = NEW.job_id
          AND existing_application.id IS DISTINCT FROM NEW.id
          AND (
              lower(existing_candidate.email) = lower(candidate_email)
              OR (
                  candidate_phone IS NOT NULL
                  AND existing_candidate.phone = candidate_phone
              )
              OR (
                  candidate_linkedin IS NOT NULL
                  AND rtrim(existing_candidate.linkedin_url, '/') = rtrim(candidate_linkedin, '/')
              )
          )
    ) THEN
        RAISE EXCEPTION 'duplicate applicant identity for this job'
            USING ERRCODE = '23505', CONSTRAINT = 'applications_job_identity_unique';
    END IF;

    RETURN NEW;
END;
$$;

CREATE TRIGGER applications_reject_duplicate_job_identity
    BEFORE INSERT OR UPDATE OF candidate_id, job_id
    ON public.applications
    FOR EACH ROW
    EXECUTE FUNCTION public.reject_duplicate_job_applicant_identity();
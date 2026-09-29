from datetime import date
from uuid import UUID

from fastapi import APIRouter, File, HTTPException, UploadFile, status

from backend.app.database.crud import candidates_db, interviews_db, jobs_db
from backend.app.schemas.interviews_schema import (
    InterviewRoundRead,
    InterviewRoundUpdate,
    InterviewScheduleRequest,
)
from backend.app.services.local_media_service import store_interview_recording

router = APIRouter(tags=["interviews"])


@router.get("/applications/{application_id}/interviews", response_model=list[InterviewRoundRead])
def list_interviews_route(application_id: UUID) -> list[InterviewRoundRead]:
    if candidates_db.get_application(application_id) is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="application not found")
    return interviews_db.list_interview_rounds(application_id)


@router.post(
    "/applications/{application_id}/interviews",
    response_model=InterviewRoundRead,
    status_code=status.HTTP_201_CREATED,
)
def schedule_interview_route(
    application_id: UUID,
    schedule: InterviewScheduleRequest,
) -> InterviewRoundRead:
    application = candidates_db.get_application(application_id)
    if application is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="application not found")
    if application.pipeline_status.value != "active_pipeline":
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="application is not active")
    return interviews_db.schedule_interview_round(application_id, schedule)


@router.patch("/interviews/{interview_id}", response_model=InterviewRoundRead)
def update_interview_route(
    interview_id: UUID,
    update: InterviewRoundUpdate,
) -> InterviewRoundRead:
    row = interviews_db.update_interview_round(interview_id, update)
    if row is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="interview not found")
    return row


@router.post("/interviews/{interview_id}/recording", response_model=InterviewRoundRead)
def upload_recording_route(
    interview_id: UUID,
    interview_date: date,
    recording: UploadFile = File(...),
) -> InterviewRoundRead:
    interview = interviews_db.get_interview_round(interview_id)
    if interview is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="interview not found")
    application = candidates_db.get_application(interview.application_id)
    if application is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="application not found")
    candidate = candidates_db.get_candidate(application.candidate_id)
    job = jobs_db.get_job(application.job_id)
    if candidate is None or job is None:
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="interview context unavailable")
    try:
        result = store_interview_recording(
            recording.file,
            interview_id=interview_id,
            job_title=job.title,
            candidate_name=candidate.full_name,
            interview_date=interview_date,
            sequence_order=interview.sequence_order,
        )
        saved = interviews_db.save_recording_reference(result)
    except (FileExistsError, ValueError, OSError) as error:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(error)) from error
    if saved is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="interview not found")
    return saved
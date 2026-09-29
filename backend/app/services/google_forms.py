from pathlib import Path
from typing import Any, Callable

from google.oauth2.service_account import Credentials
from googleapiclient.discovery import build

from backend.app.config import Settings, settings
from backend.app.prompts.form_prompts import (
    FORM_QUESTION_SYSTEM_PROMPT,
    build_form_questions_user_prompt,
)
from backend.app.schemas.google_forms_schema import (
    GoogleFormCloneRequest,
    GoogleFormCloneResult,
    GoogleFormQuestion,
    GoogleFormQuestionSet,
    GoogleFormQuestionType,
)
from backend.app.schemas.jobs_schema import JobCreate


class GoogleFormsConfigurationError(RuntimeError):
    """Raised when Google Forms settings or credentials are unavailable."""


class GoogleFormsIntegrationError(RuntimeError):
    """Raised when a Drive or Forms API operation fails."""


_GOOGLE_SCOPES = (
    "https://www.googleapis.com/auth/drive",
    "https://www.googleapis.com/auth/forms.body",
)


class GoogleFormsService:
    def __init__(
        self,
        *,
        settings_provider: Callable[[], Settings] = lambda: settings,
        drive_service: Any | None = None,
        forms_service: Any | None = None,
        service_builder: Callable[..., Any] = build,
        credentials_factory: Callable[..., Any] = Credentials.from_service_account_file,
    ) -> None:
        self._settings_provider = settings_provider
        self._drive_service = drive_service
        self._forms_service = forms_service
        self._service_builder = service_builder
        self._credentials_factory = credentials_factory

    def generate_and_clone_application_form(
        self,
        job: JobCreate,
        ai_provider: Any,
    ) -> GoogleFormCloneResult:
        generated = ai_provider.generate_structured(
            system_instruction=FORM_QUESTION_SYSTEM_PROMPT,
            user_content=build_form_questions_user_prompt(job),
            response_model=GoogleFormQuestionSet,
        )
        question_set = GoogleFormQuestionSet.model_validate(generated)
        return self.clone_application_form(
            GoogleFormCloneRequest(
                title=f"{job.title} Application",
                questions=question_set.questions,
            )
        )

    def clone_application_form(
        self,
        request: GoogleFormCloneRequest,
    ) -> GoogleFormCloneResult:
        configuration = self._settings_provider()
        template_id = request.template_file_id or configuration.google_form_template_id
        folder_id = request.destination_folder_id or configuration.google_drive_folder_id
        if not template_id:
            raise GoogleFormsConfigurationError("GOOGLE_FORM_TEMPLATE_ID is required")

        drive_service, forms_service = self._get_services(configuration)
        copied_file_id: str | None = None
        try:
            copied_file = (
                drive_service.files()
                .copy(
                    fileId=template_id,
                    body={
                        "name": request.title,
                        **({"parents": [folder_id]} if folder_id else {}),
                    },
                )
                .execute()
            )
            copied_file_id = copied_file.get("id") if isinstance(copied_file, dict) else None
            if not isinstance(copied_file_id, str) or not copied_file_id.strip():
                raise GoogleFormsIntegrationError("Drive did not return the copied form ID")

            existing_form = (
                forms_service.forms().get(formId=copied_file_id).execute()
            )
            existing_items = existing_form.get("items", [])
            if not isinstance(existing_items, list):
                raise GoogleFormsIntegrationError("Copied form returned invalid items")

            batch_requests: list[dict[str, object]] = [
                {
                    "updateFormInfo": {
                        "info": {"title": request.title},
                        "updateMask": "title",
                    }
                }
            ]
            first_new_index = len(existing_items)
            for offset, question in enumerate(request.questions):
                batch_requests.append(
                    {
                        "createItem": {
                            "item": self._question_item(question),
                            "location": {"index": first_new_index + offset},
                        }
                    }
                )

            (
                forms_service.forms()
                .batchUpdate(
                    formId=copied_file_id,
                    body={"requests": batch_requests},
                )
                .execute()
            )
            updated_form = forms_service.forms().get(formId=copied_file_id).execute()
            responder_url = updated_form.get("responderUri")
            if not isinstance(responder_url, str) or not responder_url.strip():
                raise GoogleFormsIntegrationError("Forms API did not return a responder URL")

            return GoogleFormCloneResult(
                form_id=copied_file_id,
                responder_url=responder_url,
                questions_added=len(request.questions),
            )
        except GoogleFormsIntegrationError:
            self._delete_partial_copy(drive_service, copied_file_id)
            raise
        except Exception:
            self._delete_partial_copy(drive_service, copied_file_id)
            raise GoogleFormsIntegrationError(
                "Google Drive or Forms API operation failed"
            ) from None

    def _get_services(self, configuration: Settings) -> tuple[Any, Any]:
        if self._drive_service is not None and self._forms_service is not None:
            return self._drive_service, self._forms_service

        credential_file = configuration.google_service_account_file
        if credential_file is None or not credential_file.is_file():
            raise GoogleFormsConfigurationError(
                "GOOGLE_SERVICE_ACCOUNT_FILE must point to a readable credential file"
            )
        try:
            credentials = self._credentials_factory(
                str(credential_file), scopes=list(_GOOGLE_SCOPES)
            )
            if self._drive_service is None:
                self._drive_service = self._service_builder(
                    "drive", "v3", credentials=credentials, cache_discovery=False
                )
            if self._forms_service is None:
                self._forms_service = self._service_builder(
                    "forms", "v1", credentials=credentials, cache_discovery=False
                )
        except Exception:
            raise GoogleFormsConfigurationError(
                "Google service-account client initialization failed"
            ) from None
        return self._drive_service, self._forms_service

    @staticmethod
    def _question_item(question: GoogleFormQuestion) -> dict[str, object]:
        question_body: dict[str, object] = {"required": question.required}
        if question.question_type in {
            GoogleFormQuestionType.short_text,
            GoogleFormQuestionType.paragraph,
        }:
            question_body["textQuestion"] = {
                "paragraph": question.question_type is GoogleFormQuestionType.paragraph
            }
        else:
            choice_type = (
                "RADIO"
                if question.question_type is GoogleFormQuestionType.multiple_choice
                else "CHECKBOX"
            )
            question_body["choiceQuestion"] = {
                "type": choice_type,
                "options": [{"value": option} for option in question.options],
                "shuffle": False,
            }
        return {
            "title": question.title,
            "questionItem": {"question": question_body},
        }

    @staticmethod
    def _delete_partial_copy(drive_service: Any, copied_file_id: str | None) -> None:
        if copied_file_id is None:
            return
        try:
            drive_service.files().delete(fileId=copied_file_id).execute()
        except Exception:
            pass
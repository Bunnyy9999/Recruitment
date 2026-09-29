from pathlib import Path
from typing import Any, Callable
import logging

from google.auth.transport.requests import Request
from google_auth_oauthlib.flow import InstalledAppFlow
from google.oauth2.credentials import Credentials as OAuthCredentials
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
_LOGGER = logging.getLogger(__name__)


class GoogleFormsService:
    def __init__(
        self,
        *,
        settings_provider: Callable[[], Settings] = lambda: settings,
        drive_service: Any | None = None,
        forms_service: Any | None = None,
        service_builder: Callable[..., Any] = build,
        credentials_factory: Callable[..., Any] = Credentials.from_service_account_file,
        oauth_flow_factory: Callable[..., Any] = InstalledAppFlow.from_client_secrets_file,
    ) -> None:
        self._settings_provider = settings_provider
        self._drive_service = drive_service
        self._forms_service = forms_service
        self._service_builder = service_builder
        self._credentials_factory = credentials_factory
        self._oauth_flow_factory = oauth_flow_factory

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
                    supportsAllDrives=True,
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
                editor_url=f"https://docs.google.com/forms/d/{copied_file_id}/edit",
                questions_added=len(request.questions),
            )
        except GoogleFormsIntegrationError:
            self._delete_partial_copy(drive_service, copied_file_id)
            raise
        except Exception as error:
            response = getattr(error, "resp", None)
            provider_status = getattr(response, "status", None)
            provider_reason = getattr(error, "reason", None)
            _LOGGER.error(
                "Google Form clone failed during provider operation: type=%s status=%s reason=%s",
                type(error).__name__,
                provider_status,
                provider_reason,
            )
            self._delete_partial_copy(drive_service, copied_file_id)
            if (
                provider_status == 403
                and isinstance(provider_reason, str)
                and "storage quota" in provider_reason.lower()
            ):
                raise GoogleFormsIntegrationError(
                    "The service account has no available My Drive storage quota. "
                    "Set GOOGLE_DRIVE_FOLDER_ID to a folder inside a Shared Drive "
                    "where the service account has Content manager access, or use "
                    "Workspace domain-wide delegation."
                ) from None
            raise GoogleFormsIntegrationError(
                f"Google Drive or Forms API operation failed ({type(error).__name__})"
            ) from None

    def _get_services(self, configuration: Settings) -> tuple[Any, Any]:
        if self._drive_service is not None and self._forms_service is not None:
            return self._drive_service, self._forms_service

        try:
            if configuration.google_oauth_client_file is not None:
                credentials = self._load_oauth_credentials(configuration)
            else:
                credential_file = configuration.google_service_account_file
                if credential_file is None or not credential_file.is_file():
                    raise GoogleFormsConfigurationError(
                        "Set GOOGLE_OAUTH_CLIENT_FILE or provide a readable "
                        "GOOGLE_SERVICE_ACCOUNT_FILE"
                    )
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
        except GoogleFormsConfigurationError:
            raise
        except Exception:
            raise GoogleFormsConfigurationError(
                "Google client initialization failed"
            ) from None
        return self._drive_service, self._forms_service

    def _load_oauth_credentials(self, configuration: Settings) -> OAuthCredentials:
        client_file = configuration.google_oauth_client_file
        token_file = configuration.google_oauth_token_file
        if client_file is None or not client_file.is_file():
            raise GoogleFormsConfigurationError(
                "GOOGLE_OAUTH_CLIENT_FILE must point to a readable OAuth client JSON file"
            )
        if token_file is None:
            raise GoogleFormsConfigurationError(
                "GOOGLE_OAUTH_TOKEN_FILE is required when OAuth is enabled"
            )

        credentials: OAuthCredentials | None = None
        if token_file.is_file():
            try:
                credentials = OAuthCredentials.from_authorized_user_file(
                    str(token_file), scopes=list(_GOOGLE_SCOPES)
                )
            except (ValueError, OSError):
                credentials = None

        if credentials is not None and credentials.valid:
            return credentials
        if credentials is not None and credentials.expired and credentials.refresh_token:
            credentials.refresh(Request())
        else:
            flow = self._oauth_flow_factory(str(client_file), scopes=list(_GOOGLE_SCOPES))
            credentials = flow.run_local_server(
                port=0,
                access_type="offline",
                prompt="consent",
            )

        token_file.parent.mkdir(parents=True, exist_ok=True)
        token_file.write_text(credentials.to_json(), encoding="utf-8")
        return credentials

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
            drive_service.files().delete(
                fileId=copied_file_id,
                supportsAllDrives=True,
            ).execute()
        except Exception:
            pass
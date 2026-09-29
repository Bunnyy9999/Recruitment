from datetime import date
from io import BytesIO
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest import TestCase
from uuid import uuid4

from backend.app.config import Settings
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
from backend.app.services.google_forms import (
    GoogleFormsConfigurationError,
    GoogleFormsIntegrationError,
    GoogleFormsService,
)
from backend.app.services.local_media_service import store_interview_recording


class FakeRequest:
    def __init__(self, response: object = None, error: Exception | None = None):
        self.response = response
        self.error = error

    def execute(self) -> object:
        if self.error is not None:
            raise self.error
        return self.response


class FakeDriveFiles:
    def __init__(self, copied_file: dict[str, object], error: Exception | None = None):
        self.copied_file = copied_file
        self.error = error
        self.copy_calls: list[dict[str, object]] = []
        self.deleted_ids: list[str] = []

    def copy(self, **kwargs: object) -> FakeRequest:
        self.copy_calls.append(kwargs)
        return FakeRequest(self.copied_file, self.error)

    def delete(self, *, fileId: str, **kwargs: object) -> FakeRequest:
        self.deleted_ids.append(fileId)
        return FakeRequest({})


class FakeDriveService:
    def __init__(self, files: FakeDriveFiles):
        self._files = files

    def files(self) -> FakeDriveFiles:
        return self._files


class FakeFormsService:
    def __init__(self, responder_url: str):
        self.responder_url = responder_url
        self.batch_calls: list[dict[str, object]] = []
        self.get_calls: list[dict[str, object]] = []

    def forms(self) -> "FakeFormsService":
        return self

    def get(self, *, formId: str) -> FakeRequest:
        self.get_calls.append({"formId": formId})
        if len(self.get_calls) == 1:
            return FakeRequest({"items": [{"itemId": "existing-item"}]})
        return FakeRequest({"responderUri": self.responder_url})

    def batchUpdate(self, **kwargs: object) -> FakeRequest:
        self.batch_calls.append(kwargs)
        return FakeRequest({"replies": []})


class GoogleFormSchemaTests(TestCase):
    def test_choice_questions_require_multiple_unique_options(self) -> None:
        with self.assertRaises(ValueError):
            GoogleFormQuestion(
                title="Preferred language",
                question_type=GoogleFormQuestionType.multiple_choice,
                options=["Python"],
            )
        with self.assertRaises(ValueError):
            GoogleFormQuestion(
                title="Preferred language",
                question_type=GoogleFormQuestionType.multiple_choice,
                options=["Python", "Python"],
            )

    def test_text_question_rejects_choice_options(self) -> None:
        with self.assertRaises(ValueError):
            GoogleFormQuestion(
                title="Describe your experience",
                question_type=GoogleFormQuestionType.paragraph,
                options=["Option A", "Option B"],
            )

    def test_clone_request_rejects_unknown_fields(self) -> None:
        with self.assertRaises(ValueError):
            GoogleFormCloneRequest(
                title="Data Engineer Application",
                questions=[
                    GoogleFormQuestion(
                        title="Describe your experience",
                        question_type=GoogleFormQuestionType.paragraph,
                    )
                ],
                unexpected="not allowed",
            )


class FormQuestionPromptTests(TestCase):
    def test_prompt_payload_contains_supplied_job_criteria(self) -> None:
        job = JobCreate(
            title="Data Engineer",
            tech_stack="Python, PostgreSQL, Airflow",
            seniority="Senior",
            compensation_min=120000,
            compensation_max=160000,
        )

        payload = build_form_questions_user_prompt(job)

        self.assertIn("Data Engineer", payload)
        self.assertIn("PostgreSQL", payload)
        self.assertIn("Airflow", payload)
        self.assertIn("role-specific", FORM_QUESTION_SYSTEM_PROMPT.lower())
        self.assertIn("fixed question list", FORM_QUESTION_SYSTEM_PROMPT.lower())


class FakeTextAIProvider:
    def __init__(self, response: object):
        self.response = response
        self.calls: list[dict[str, object]] = []

    def generate_structured(self, **kwargs: object) -> object:
        self.calls.append(kwargs)
        return self.response


class FormQuestionGenerationTests(TestCase):
    def test_generated_questions_are_passed_to_cloned_form(self) -> None:
        questions = [
            GoogleFormQuestion(
                title="How have you used Airflow to orchestrate production pipelines?",
                question_type=GoogleFormQuestionType.paragraph,
            ),
            GoogleFormQuestion(
                title="Which SQL databases have you used at scale?",
                question_type=GoogleFormQuestionType.multiple_choice,
                options=["PostgreSQL", "MySQL", "Other"],
            ),
        ]
        question_set = GoogleFormQuestionSet(questions=questions)
        provider = FakeTextAIProvider(question_set)
        drive_files = FakeDriveFiles({"id": "copied-form-id"})
        drive = FakeDriveService(drive_files)
        forms = FakeFormsService(
            "https://docs.google.com/forms/d/copied-form-id/viewform"
        )
        settings = Settings(
            _env_file=None,
            google_form_template_id="template-id",
            google_drive_folder_id="folder-id",
        )
        service = GoogleFormsService(
            settings_provider=lambda: settings,
            drive_service=drive,
            forms_service=forms,
        )
        job = JobCreate(
            title="Data Engineer",
            tech_stack="Python, PostgreSQL, Airflow",
            seniority="Senior",
        )

        result = service.generate_and_clone_application_form(job, provider)

        self.assertEqual(
            str(result.responder_url),
            "https://docs.google.com/forms/d/copied-form-id/viewform",
        )
        self.assertIn("Airflow", provider.calls[0]["user_content"])
        request_items = forms.batch_calls[0]["body"]["requests"]
        self.assertEqual(len(request_items), 3)


class GoogleFormsServiceTests(TestCase):
    def setUp(self) -> None:
        self.drive_files = FakeDriveFiles({"id": "copied-form-id"})
        self.drive = FakeDriveService(self.drive_files)
        self.forms = FakeFormsService(
            "https://docs.google.com/forms/d/copied-form-id/viewform"
        )
        self.service = GoogleFormsService(
            drive_service=self.drive,
            forms_service=self.forms,
        )

    def test_clones_form_and_appends_typed_questions(self) -> None:
        request = GoogleFormCloneRequest(
            template_file_id="template-id",
            destination_folder_id="folder-id",
            title="Data Engineer Application",
            questions=[
                GoogleFormQuestion(
                    title="Describe your production Python experience",
                    question_type=GoogleFormQuestionType.paragraph,
                ),
                GoogleFormQuestion(
                    title="Which database have you used?",
                    question_type=GoogleFormQuestionType.multiple_choice,
                    options=["PostgreSQL", "MySQL"],
                ),
            ],
        )

        result = self.service.clone_application_form(request)

        self.assertIsInstance(result, GoogleFormCloneResult)
        self.assertEqual(result.form_id, "copied-form-id")
        self.assertEqual(
            str(result.responder_url),
            "https://docs.google.com/forms/d/copied-form-id/viewform",
        )
        self.assertEqual(
            self.drive_files.copy_calls[0]["fileId"], "template-id"
        )
        self.assertEqual(
            self.drive_files.copy_calls[0]["body"],
            {
                "name": "Data Engineer Application",
                "parents": ["folder-id"],
            },
        )

        requests = self.forms.batch_calls[0]["body"]["requests"]
        self.assertEqual(requests[0]["updateFormInfo"]["info"]["title"], "Data Engineer Application")
        self.assertEqual(requests[0]["updateFormInfo"]["updateMask"], "title")
        self.assertEqual(requests[1]["createItem"]["location"]["index"], 1)
        self.assertEqual(
            requests[1]["createItem"]["item"]["questionItem"]["question"]["textQuestion"],
            {"paragraph": True},
        )
        self.assertEqual(requests[2]["createItem"]["location"]["index"], 2)
        self.assertEqual(
            requests[2]["createItem"]["item"]["questionItem"]["question"]["choiceQuestion"]["type"],
            "RADIO",
        )

    def test_service_uses_global_template_and_folder_settings(self) -> None:
        settings = Settings(
            _env_file=None,
            google_form_template_id="configured-template",
            google_drive_folder_id="configured-folder",
        )
        service = GoogleFormsService(
            settings_provider=lambda: settings,
            drive_service=self.drive,
            forms_service=self.forms,
        )
        request = GoogleFormCloneRequest(
            title="Configured Form",
            questions=[
                GoogleFormQuestion(
                    title="Tell us about your experience",
                    question_type=GoogleFormQuestionType.paragraph,
                )
            ],
        )

        service.clone_application_form(request)

        self.assertEqual(self.drive_files.copy_calls[0]["fileId"], "configured-template")
        self.assertEqual(
            self.drive_files.copy_calls[0]["body"]["parents"], ["configured-folder"]
        )

    def test_missing_template_or_credentials_fails_before_api_call(self) -> None:
        settings = Settings(_env_file=None)
        service = GoogleFormsService(settings_provider=lambda: settings)
        request = GoogleFormCloneRequest(
            title="Data Engineer Application",
            questions=[
                GoogleFormQuestion(
                    title="Describe your experience",
                    question_type=GoogleFormQuestionType.paragraph,
                )
            ],
        )

        with self.assertRaises(GoogleFormsConfigurationError):
            service.clone_application_form(request)

    def test_google_api_error_is_sanitized(self) -> None:
        files = FakeDriveFiles(
            {"id": ""},
            error=RuntimeError("sensitive provider response payload"),
        )
        service = GoogleFormsService(
            drive_service=FakeDriveService(files),
            forms_service=self.forms,
        )
        request = GoogleFormCloneRequest(
            template_file_id="template-id",
            title="Data Engineer Application",
            questions=[
                GoogleFormQuestion(
                    title="Describe your experience",
                    question_type=GoogleFormQuestionType.paragraph,
                )
            ],
        )

        with self.assertRaises(GoogleFormsIntegrationError) as raised:
            service.clone_application_form(request)

        self.assertNotIn("sensitive provider response", str(raised.exception))


class LocalMediaServiceTests(TestCase):
    def test_stores_and_verifies_interview_recording(self) -> None:
        interview_id = uuid4()
        with TemporaryDirectory() as temporary_directory:
            result = store_interview_recording(
                BytesIO(b"recording bytes are stored without decoding"),
                interview_id=interview_id,
                job_title="Data Engineer",
                candidate_name="Alex Doe",
                interview_date=date(2026, 10, 1),
                sequence_order=2,
                recordings_root=Path(temporary_directory),
            )

            self.assertEqual(result.interview_id, interview_id)
            self.assertEqual(result.sequence_order, 2)
            self.assertTrue(result.recording_verified)
            self.assertTrue(Path(result.local_audio_path).is_file())
            self.assertIn("technical_interview_2.mp3", result.local_audio_path)

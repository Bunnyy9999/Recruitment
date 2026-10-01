import os
from types import SimpleNamespace
from unittest import TestCase
from unittest.mock import patch

from pydantic import SecretStr

from backend.app.config import Settings
from backend.app.schemas.candidates_schema import ApplicationScreeningResult
from backend.app.services.ai.base import (
    AIConfigurationError,
    AIProviderError,
    AIResponseError,
    TextAIProvider,
)
from backend.app.services.ai.gemini_flash import GeminiFlashProvider


class FakeInteractions:
    def __init__(
        self,
        output_text: str | None = None,
        error: Exception | None = None,
        usage: SimpleNamespace | None = None,
        events: list[str] | None = None,
    ):
        self.output_text = output_text
        self.error = error
        self.usage = usage
        self.events = events
        self.calls: list[dict[str, object]] = []

    def create(self, **kwargs: object) -> SimpleNamespace:
        self.calls.append(kwargs)
        if self.events is not None:
            self.events.append("request")
        if self.error is not None:
            raise self.error
        return SimpleNamespace(output_text=self.output_text, usage=self.usage)


class FakeClient:
    def __init__(self, interactions: FakeInteractions):
        self.interactions = interactions


class ProviderConfigurationTests(TestCase):
    def test_settings_load_gemini_key_model_and_recordings_root(self) -> None:
        with patch.dict(
            os.environ,
            {
                "GEMINI_API_KEY": "test-secret-key",
                "GEMINI_MODEL": "gemini-test-model",
                "RECORDINGS_DIR": "./test-recordings",
            },
        ):
            settings = Settings(_env_file=None)

        self.assertEqual(
            settings.gemini_api_key,
            SecretStr("test-secret-key"),
        )
        self.assertEqual(settings.gemini_model, "gemini-test-model")
        self.assertTrue(settings.recordings_dir.name == "test-recordings")
        self.assertNotIn("test-secret-key", repr(settings))

    def test_missing_api_key_raises_configuration_error(self) -> None:
        with patch("backend.app.services.ai.gemini_flash.settings") as config:
            config.gemini_api_key = None
            config.gemini_model = "gemini-test-model"

            with self.assertRaises(AIConfigurationError):
                GeminiFlashProvider()


class FakeObservation:
    def __init__(self, langfuse: "FakeLangfuse", **kwargs: object):
        self.langfuse = langfuse
        self.kwargs = kwargs
        self.updates: list[dict[str, object]] = []

    def __enter__(self) -> "FakeObservation":
        self.langfuse.events.append("enter")
        return self

    def __exit__(self, exc_type: object, exc: object, tb: object) -> bool:
        self.langfuse.events.append("exit")
        return False

    def update(self, **kwargs: object) -> None:
        self.updates.append(kwargs)


class FakeLangfuse:
    def __init__(self):
        self.observations: list[dict[str, object]] = []
        self.events: list[str] = []
        self.handles: list[FakeObservation] = []

    def start_as_current_observation(self, **kwargs: object) -> FakeObservation:
        self.observations.append(kwargs)
        observation = FakeObservation(self, **kwargs)
        self.handles.append(observation)
        return observation


class GeminiAdapterTests(TestCase):
    def test_settings_load_langfuse_keys(self) -> None:
        with patch.dict(
            os.environ,
            {
                "LANGFUSE_PUBLIC_KEY": "pk-lf-test",
                "LANGFUSE_SECRET_KEY": "sk-lf-test",
                "LANGFUSE_BASE_URL": "https://us.cloud.langfuse.com",
            },
            clear=False,
        ):
            settings = Settings(_env_file=None)

        self.assertEqual(settings.langfuse_public_key, "pk-lf-test")
        self.assertEqual(settings.langfuse_secret_key, SecretStr("sk-lf-test"))
        self.assertEqual(settings.langfuse_base_url, "https://us.cloud.langfuse.com")

    def test_adapter_satisfies_provider_protocol(self) -> None:
        adapter = GeminiFlashProvider(
            client=FakeClient(FakeInteractions("JD draft")),
            model="gemini-test-model",
        )
        self.assertIsInstance(adapter, TextAIProvider)

    def test_generate_text_records_langfuse_generation(self) -> None:
        langfuse = FakeLangfuse()
        interactions = FakeInteractions(
            "JD draft",
            usage=SimpleNamespace(total_input_tokens=24, total_output_tokens=8),
            events=langfuse.events,
        )
        adapter = GeminiFlashProvider(
            client=FakeClient(interactions),
            model="gemini-test-model",
            langfuse=langfuse,
        )

        adapter.generate_text(
            system_instruction="Write a factual JD.",
            user_content='{"title":"Data Engineer"}',
        )

        self.assertTrue(langfuse.observations)
        self.assertEqual(langfuse.observations[0]["as_type"], "generation")
        self.assertEqual(langfuse.observations[0]["name"], "gemini.generate_text")
        self.assertEqual(langfuse.observations[0]["model"], "gemini-test-model")
        self.assertEqual(langfuse.events, ["enter", "request", "exit"])
        self.assertEqual(
            langfuse.handles[0].updates[0]["usage_details"],
            {"input": 24, "output": 8},
        )
        self.assertEqual(langfuse.handles[0].updates[0]["output"], "JD draft")

    def test_generate_text_uses_configured_model_and_disables_storage(self) -> None:
        interactions = FakeInteractions("# Data Engineer")
        adapter = GeminiFlashProvider(
            client=FakeClient(interactions),
            model="gemini-test-model",
        )

        result = adapter.generate_text(
            system_instruction="Write a factual JD.",
            user_content='{"title":"Data Engineer"}',
        )

        self.assertEqual(result, "# Data Engineer")
        self.assertEqual(
            interactions.calls[0],
            {
                "model": "gemini-test-model",
                "system_instruction": "Write a factual JD.",
                "input": '{"title":"Data Engineer"}',
                "store": False,
            },
        )

    def test_generate_structured_validates_pydantic_result(self) -> None:
        interactions = FakeInteractions(
            '{"agent_decision":"pass",'
            '"screening_summary":"Evidence supports required Python experience."}'
        )
        adapter = GeminiFlashProvider(
            client=FakeClient(interactions),
            model="gemini-test-model",
        )

        result = adapter.generate_structured(
            system_instruction="Return screening output JSON.",
            user_content="screening input",
            response_model=ApplicationScreeningResult,
        )

        self.assertEqual(result.agent_decision.value, "pass")
        self.assertEqual(
            interactions.calls[0]["response_format"],
            {
                "type": "text",
                "mime_type": "application/json",
                "schema": ApplicationScreeningResult.model_json_schema(),
            },
        )
        self.assertFalse(interactions.calls[0]["store"])

    def test_invalid_structured_response_fails_closed(self) -> None:
        interactions = FakeInteractions(
            '{"agent_decision":"maybe","screening_summary":"unclear"}'
        )
        adapter = GeminiFlashProvider(
            client=FakeClient(interactions),
            model="gemini-test-model",
        )

        with self.assertRaises(AIResponseError):
            adapter.generate_structured(
                system_instruction="Return screening output JSON.",
                user_content="screening input",
                response_model=ApplicationScreeningResult,
            )

    def test_empty_response_fails_closed(self) -> None:
        adapter = GeminiFlashProvider(
            client=FakeClient(FakeInteractions("  ")),
            model="gemini-test-model",
        )

        with self.assertRaises(AIResponseError):
            adapter.generate_text(
                system_instruction="Write a factual JD.",
                user_content="job input",
            )

    def test_provider_failure_is_wrapped_without_candidate_content(self) -> None:
        interactions = FakeInteractions(error=RuntimeError("sensitive payload text"))
        adapter = GeminiFlashProvider(
            client=FakeClient(interactions),
            model="gemini-test-model",
        )

        with self.assertRaises(AIProviderError) as raised:
            adapter.generate_text(
                system_instruction="Write a factual JD.",
                user_content="candidate data must not leak into error",
            )

        self.assertNotIn("sensitive payload text", str(raised.exception))
        self.assertNotIn("candidate data", str(raised.exception))

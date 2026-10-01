from typing import Any, TypeVar

from google import genai
from pydantic import BaseModel, SecretStr, ValidationError

from backend.app.config import settings
from backend.app.services.ai.base import (
    AIConfigurationError,
    AIProviderError,
    AIResponseError,
)
from backend.app.services.langfuse_service import build_langfuse_client


ResponseModel = TypeVar("ResponseModel", bound=BaseModel)


class GeminiFlashProvider:
    def __init__(
        self,
        *,
        api_key: str | SecretStr | None = None,
        model: str | None = None,
        client: Any | None = None,
        langfuse: Any | None = None,
    ) -> None:
        selected_model = settings.gemini_model if model is None else model
        if not isinstance(selected_model, str) or not selected_model.strip():
            raise AIConfigurationError("Gemini model configuration is invalid")
        self._model = selected_model.strip()
        self._langfuse = build_langfuse_client() if langfuse is None else langfuse

        if client is not None:
            self._client = client
            return

        selected_key = settings.gemini_api_key if api_key is None else api_key
        if isinstance(selected_key, SecretStr):
            selected_key = selected_key.get_secret_value()
        if not isinstance(selected_key, str) or not selected_key.strip():
            raise AIConfigurationError("GEMINI_API_KEY is required for Gemini calls")

        try:
            self._client = genai.Client(api_key=selected_key.strip())
        except Exception as error:
            raise AIConfigurationError("Gemini client configuration failed") from error

    def generate_text(
        self,
        *,
        system_instruction: str,
        user_content: str,
    ) -> str:
        return self._generate_observed(
            operation="generate_text",
            system_instruction=system_instruction,
            user_content=user_content,
        )

    def generate_structured(
        self,
        *,
        system_instruction: str,
        user_content: str,
        response_model: type[ResponseModel],
    ) -> ResponseModel:
        response_format = {
            "type": "text",
            "mime_type": "application/json",
            "schema": response_model.model_json_schema(),
        }
        output_text = self._generate_observed(
            operation="generate_structured",
            system_instruction=system_instruction,
            user_content=user_content,
            response_format=response_format,
            metadata={"response_model": response_model.__name__},
        )

        try:
            return response_model.model_validate_json(output_text)
        except (ValidationError, ValueError, TypeError) as error:
            raise AIResponseError(
                "Gemini structured response did not match the requested schema"
            ) from error

    def _create_interaction(
        self,
        *,
        system_instruction: str,
        user_content: str,
        response_format: dict[str, object] | None = None,
    ) -> Any:
        if not isinstance(system_instruction, str) or not system_instruction.strip():
            raise ValueError("system_instruction must be a non-empty string")
        if not isinstance(user_content, str) or not user_content.strip():
            raise ValueError("user_content must be a non-empty string")

        request: dict[str, object] = {
            "model": self._model,
            "system_instruction": system_instruction,
            "input": user_content,
            "store": False,
        }
        if response_format is not None:
            request["response_format"] = response_format

        try:
            return self._client.interactions.create(**request)
        except Exception as error:
            raise AIProviderError("Gemini request failed") from error

    @staticmethod
    def _read_output_text(interaction: Any) -> str:
        output_text = getattr(interaction, "output_text", None)
        if not isinstance(output_text, str) or not output_text.strip():
            raise AIResponseError("Gemini returned an empty or non-text response")
        return output_text.strip()

    def _generate_observed(
        self,
        *,
        operation: str,
        system_instruction: str,
        user_content: str,
        response_format: dict[str, object] | None = None,
        metadata: dict[str, object] | None = None,
    ) -> str:
        payload_metadata = {
            "provider": "gemini",
            "model": self._model,
            "response_type": operation,
            **(metadata or {}),
        }
        input_payload = {
            "system_instruction": self._truncate_payload(system_instruction),
            "user_content": self._truncate_payload(user_content),
        }
        if self._langfuse is None:
            interaction = self._create_interaction(
                system_instruction=system_instruction,
                user_content=user_content,
                response_format=response_format,
            )
            return self._read_output_text(interaction)

        try:
            observation_context = self._langfuse.start_as_current_observation(
                as_type="generation",
                name=f"gemini.{operation}",
                model=self._model,
                input=input_payload,
                metadata=payload_metadata,
            )
        except Exception:
            interaction = self._create_interaction(
                system_instruction=system_instruction,
                user_content=user_content,
                response_format=response_format,
            )
            return self._read_output_text(interaction)

        output_text: str | None = None
        try:
            with observation_context as generation:
                interaction = self._create_interaction(
                    system_instruction=system_instruction,
                    user_content=user_content,
                    response_format=response_format,
                )
                output_text = self._read_output_text(interaction)
                update: dict[str, object] = {
                    "output": self._truncate_payload(output_text),
                }
                usage_details = self._extract_usage_details(interaction)
                if usage_details:
                    update["usage_details"] = usage_details
                try:
                    generation.update(**update)
                except Exception:
                    pass
        except (AIProviderError, AIResponseError):
            raise
        except Exception:
            if output_text is None:
                interaction = self._create_interaction(
                    system_instruction=system_instruction,
                    user_content=user_content,
                    response_format=response_format,
                )
                output_text = self._read_output_text(interaction)

        return output_text

    @staticmethod
    def _extract_usage_details(interaction: Any) -> dict[str, int]:
        usage = getattr(interaction, "usage", None)
        if usage is None:
            return {}

        usage_details: dict[str, int] = {}
        for langfuse_key, gemini_key in (
            ("input", "total_input_tokens"),
            ("output", "total_output_tokens"),
        ):
            token_count = getattr(usage, gemini_key, None)
            if isinstance(token_count, int) and token_count >= 0:
                usage_details[langfuse_key] = token_count
        return usage_details

    @staticmethod
    def _truncate_payload(value: str, *, max_length: int = 12000) -> str:
        if len(value) <= max_length:
            return value
        return f"{value[:max_length]}... [truncated]"
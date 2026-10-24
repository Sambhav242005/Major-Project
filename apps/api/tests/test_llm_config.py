from core.config import Settings, settings
import asyncio
import json

import httpx
import pytest
from fastapi import HTTPException
from pydantic import ValidationError

from pipelines import llm_client
from routers.chat import GenerationSelection, SendMessageRequest


def test_chat_model_is_configurable():
    assert settings.LLM_CHAT_MODEL
    assert isinstance(settings.LLM_CHAT_MODEL, str)


def test_extract_model_is_configurable():
    assert settings.LLM_EXTRACT_MODEL
    assert isinstance(settings.LLM_EXTRACT_MODEL, str)


def test_chat_and_extract_models_are_separate_settings():
    assert hasattr(settings, "LLM_CHAT_MODEL")
    assert hasattr(settings, "LLM_EXTRACT_MODEL")


def test_chat_and_extract_models_can_be_configured_independently(monkeypatch):
    monkeypatch.setenv("LLM_CHAT_MODEL", "chat-model")
    monkeypatch.setenv("LLM_EXTRACT_MODEL", "extract-model")
    configured_settings = Settings()
    assert configured_settings.LLM_CHAT_MODEL == "chat-model"
    assert configured_settings.LLM_EXTRACT_MODEL == "extract-model"


def test_legacy_messages_keep_server_settings():
    assert SendMessageRequest(message="Hello").generation is None
    config = GenerationSelection().resolve()
    assert config.model == settings.LLM_CHAT_MODEL
    assert config.base_url == settings.LLM_BASE_URL


@pytest.mark.parametrize("provider,endpoint", [
    ("openai", "https://api.openai.com/v1"),
    ("groq", "https://api.groq.com/openai/v1"),
    ("openrouter", "https://openrouter.ai/api/v1"),
    ("gemini", "https://generativelanguage.googleapis.com/v1beta/openai"),
])
def test_selection_uses_only_selected_credentials(provider, endpoint):
    selection = GenerationSelection(provider=provider, model=" selected-model ", api_key="private-test-key")
    resolved = selection.resolve()
    assert resolved.model == "selected-model"
    assert resolved.base_url == endpoint
    assert resolved.api_key == "private-test-key"
    assert "private-test-key" not in repr(selection)
    assert "private-test-key" not in repr(resolved)


@pytest.mark.parametrize("values", [
    {"provider": "groq", "model": "model"},
    {"provider": "groq", "api_key": "test-key"},
    {"provider": "gemini", "model": "gemini-test-model"},
    {"provider": "gemini", "api_key": "test-key"},
    {"provider": "openai", "model": "model", "api_key": "bad\nkey"},
])
def test_missing_or_invalid_credentials_rejected(values):
    with pytest.raises(HTTPException) as error:
        GenerationSelection(**values).resolve()
    assert error.value.status_code == 422


@pytest.mark.parametrize("values", [
    {"provider": "unknown"}, {"model": "   "}, {"model": "bad\nmodel"},
    {"base_url": "http://untrusted.invalid"},
])
def test_invalid_selection_is_rejected(values):
    with pytest.raises(ValidationError):
        GenerationSelection(**values)


def test_chatgpt_requires_server_connection(monkeypatch):
    monkeypatch.setattr(settings, "CHATGPT_CREDENTIALS_PATH", "")
    with pytest.raises(HTTPException):
        GenerationSelection(provider="chatgpt", model="account-model").resolve()
    monkeypatch.setattr(settings, "CHATGPT_CREDENTIALS_PATH", "/private/credentials")
    assert GenerationSelection(provider="chatgpt", model="account-model").resolve().provider == "chatgpt"


@pytest.mark.asyncio
async def test_concurrent_selections_do_not_change_server_defaults(monkeypatch):
    original = (settings.LLM_PROVIDER, settings.LLM_CHAT_MODEL, settings.LLM_API_KEY, settings.LLM_BASE_URL)
    seen = []

    async def handler(request):
        await asyncio.sleep(0)
        seen.append((str(request.url), request.headers["authorization"], json.loads(request.content)["model"]))
        return httpx.Response(200, text='data: {"choices":[{"delta":{"content":"OK"}}]}\n\ndata: [DONE]\n\n')

    async def run(provider, model, key):
        config = GenerationSelection(provider=provider, model=model, api_key=key).resolve()
        return "".join([part async for part in llm_client.chat_completion_stream(
            [{"role": "user", "content": "Hello"}], generation=config,
        )])

    async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as client:
        monkeypatch.setattr(llm_client, "_get_client", lambda: client)
        assert await asyncio.gather(
            run("groq", "model-a", "key-a"),
            run("openai", "model-b", "key-b"),
            run("gemini", "gemini-test-model", "gemini-test-key"),
        ) == ["OK", "OK", "OK"]
    assert set(seen) == {
        ("https://api.groq.com/openai/v1/chat/completions", "Bearer key-a", "model-a"),
        ("https://api.openai.com/v1/chat/completions", "Bearer key-b", "model-b"),
        ("https://generativelanguage.googleapis.com/v1beta/openai/chat/completions", "Bearer gemini-test-key", "gemini-test-model"),
    }
    assert (settings.LLM_PROVIDER, settings.LLM_CHAT_MODEL, settings.LLM_API_KEY, settings.LLM_BASE_URL) == original


@pytest.mark.asyncio
async def test_selected_chatgpt_routes_independently_of_server_provider(monkeypatch):
    monkeypatch.setattr(settings, "LLM_PROVIDER", "openai")
    seen = []

    async def stream(messages, model):
        seen.append(model)
        yield "Account answer"

    monkeypatch.setattr(llm_client, "_chatgpt_completion_stream", stream)
    result = "".join([part async for part in llm_client.chat_completion_stream(
        [{"role": "user", "content": "Hello"}],
        generation=llm_client.GenerationConfig("chatgpt", "selected-account-model"),
    )])
    assert result == "Account answer"
    assert seen == ["selected-account-model"]

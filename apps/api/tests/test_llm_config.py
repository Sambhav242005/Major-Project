from core.config import settings


def test_chat_model_is_configurable():
    assert settings.LLM_CHAT_MODEL
    assert isinstance(settings.LLM_CHAT_MODEL, str)


def test_extract_model_is_configurable():
    assert settings.LLM_EXTRACT_MODEL
    assert isinstance(settings.LLM_EXTRACT_MODEL, str)


def test_chat_and_extract_models_are_separate_settings():
    assert hasattr(settings, "LLM_CHAT_MODEL")
    assert hasattr(settings, "LLM_EXTRACT_MODEL")
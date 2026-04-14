from app.config import load_settings


def test_load_settings_reads_enabled_models(monkeypatch):
    monkeypatch.setenv("LLM_GLM_API_KEY", "glm-key")
    monkeypatch.setenv("LLM_GLM_BASE_URL", "https://glm.example/v1")
    monkeypatch.setenv("LLM_GLM_MODEL", "glm-5.1")
    monkeypatch.setenv("LLM_OPENAI_API_KEY", "openai-key")
    monkeypatch.setenv("LLM_OPENAI_BASE_URL", "https://proxy.example/v1")
    monkeypatch.setenv("LLM_OPENAI_MODEL", "deepseek-v3")

    settings = load_settings(load_env=False)

    assert [model.id for model in settings.models] == ["glm", "openai"]
    assert settings.get_model("glm").protocol == "anthropic"
    assert settings.get_model("openai").protocol == "openai"


def test_load_settings_raises_when_no_model_is_configured(monkeypatch):
    monkeypatch.delenv("LLM_GLM_API_KEY", raising=False)
    monkeypatch.delenv("LLM_GLM_BASE_URL", raising=False)
    monkeypatch.delenv("LLM_GLM_MODEL", raising=False)
    monkeypatch.delenv("LLM_OPENAI_API_KEY", raising=False)
    monkeypatch.delenv("LLM_OPENAI_BASE_URL", raising=False)
    monkeypatch.delenv("LLM_OPENAI_MODEL", raising=False)

    try:
        load_settings(load_env=False)
    except RuntimeError as exc:
        assert "No LLM models configured" in str(exc)
    else:
        raise AssertionError("Expected RuntimeError when no model is configured")


def test_conversation_config_reads_from_env(monkeypatch):
    monkeypatch.setenv("CONV_MAX_MESSAGES", "30")
    monkeypatch.setenv("CONV_TTL_SECONDS", "7200")
    monkeypatch.setenv("CONV_MAX_CONVERSATIONS", "200")

    from app.config import load_conversation_config

    config = load_conversation_config(load_env=False)
    assert config["max_messages"] == 30
    assert config["ttl_seconds"] == 7200
    assert config["max_conversations"] == 200

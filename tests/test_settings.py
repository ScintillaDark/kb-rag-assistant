import pytest

from common.settings import Settings


def test_settings_from_environment_maps_local_runtime_configuration():
    settings = Settings.from_env(
        {
            "APP_ENV": "local",
            "API_KEY": " local-secret ",
            "RAG_TOP_K": "8",
            "OLLAMA_THINK": "true",
        }
    )

    assert settings.app_env == "local"
    assert settings.api_key == "local-secret"
    assert settings.top_k == 8
    assert settings.ollama_think is True
    assert "local-secret" not in repr(settings)


@pytest.mark.parametrize(
    ("values", "message"),
    [
        ({"APP_ENV": "remote"}, "APP_ENV"),
        ({"API_RATE_LIMIT_PER_MINUTE": "many"}, "API_RATE_LIMIT_PER_MINUTE"),
        ({"RAG_CLARIFICATION_ENABLED": "sometimes"}, "RAG_CLARIFICATION_ENABLED"),
        ({"RAG_TOP_K": "0"}, "top_k"),
        ({"RAG_SIMILARITY_THRESHOLD": "1.5"}, "similarity_threshold"),
    ],
)
def test_settings_reject_invalid_configuration(values, message):
    with pytest.raises(ValueError, match=message):
        Settings.from_env(values)

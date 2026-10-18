"""settings 加载与校验单测（独立 .env 文件，不读本地真实配置）。"""

from __future__ import annotations

import pytest

from app.common.errors import ConfigError
from app.settings import Settings, load_settings


def write_env(tmp_path, content: str):
    env = tmp_path / ".env"
    env.write_text(content, encoding="utf-8")
    return env


class TestSettings:
    def test_minimal_valid_env(self, tmp_path) -> None:
        env = write_env(
            tmp_path,
            "DEFAULT_LLM=glm\nGLM_API_KEY=test-key\nGLM_MODEL=glm-4-flash\n",
        )
        s = load_settings(env)
        assert s.DEFAULT_LLM == "glm"
        assert s.configured_providers == ["glm"]
        assert s.provider_config("glm")["api_key"] == "test-key"
        assert s.provider_config("glm")["model"] == "glm-4-flash"

    def test_default_llm_fallback_to_first_configured(self, tmp_path) -> None:
        env = write_env(tmp_path, "DEFAULT_LLM=deepseek\nGLM_API_KEY=k\nGLM_MODEL=m\n")
        s = load_settings(env)
        # deepseek 未配 Key → 回退 glm
        assert s.DEFAULT_LLM == "glm"

    def test_no_key_allowed(self, tmp_path) -> None:
        """不配置任何 API Key 也能启动：仅本地对弈与建议，无 LLM 解说。"""
        env = write_env(tmp_path, "DEFAULT_LLM=deepseek\n")
        s = load_settings(env)
        assert s.configured_providers == []
        assert s.DEFAULT_LLM == "deepseek"

    def test_invalid_default_llm_rejected(self, tmp_path) -> None:
        env = write_env(tmp_path, "DEFAULT_LLM=unknown\nGLM_API_KEY=k\n")
        with pytest.raises(ConfigError):
            load_settings(env)

    def test_unknown_provider_config(self, tmp_path) -> None:
        env = write_env(tmp_path, "GLM_API_KEY=k\n")
        s = load_settings(env)
        with pytest.raises(ConfigError):
            s.provider_config("nonexistent")

    def test_defaults_for_urls(self, tmp_path) -> None:
        env = write_env(tmp_path, "GLM_API_KEY=k\n")
        s = load_settings(env)
        cfg = s.provider_config("kimi")
        assert cfg["base_url"] == "https://api.moonshot.cn/v1"
        assert cfg["model"] == "moonshot-v1-8k"
        assert cfg["api_key"] == ""

    def test_direct_construction_without_key(self) -> None:
        """直接构造 Settings 时，没有 Key 也不再报校验错误。"""
        s = Settings(_env_file=None, DEEPSEEK_API_KEY="")  # type: ignore[call-arg]
        assert s.configured_providers == []

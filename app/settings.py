"""配置加载与校验：pydantic-settings 从 .env 读取。

API Key 是可选的：不配置任何 Key 时仍可正常启动，
此时只有本地 AI 对弈与本地落子建议，不进行 LLM 解说。
"""

from __future__ import annotations

from pathlib import Path

from pydantic import field_validator, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

from app.common.errors import ConfigError

PROVIDERS = ("deepseek", "kimi", "glm", "doubao")


class Settings(BaseSettings):
    """应用全局配置（.env 或环境变量）。"""

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    DEFAULT_LLM: str = "deepseek"

    DEEPSEEK_API_KEY: str = ""
    DEEPSEEK_BASE_URL: str = "https://api.deepseek.com"
    DEEPSEEK_MODEL: str = "deepseek-chat"

    KIMI_API_KEY: str = ""
    KIMI_BASE_URL: str = "https://api.moonshot.cn/v1"
    KIMI_MODEL: str = "moonshot-v1-8k"

    GLM_API_KEY: str = ""
    GLM_BASE_URL: str = "https://open.bigmodel.cn/api/paas/v4"
    GLM_MODEL: str = "glm-4-flash"

    DOUBAO_API_KEY: str = ""
    DOUBAO_BASE_URL: str = "https://ark.cn-beijing.volces.com/api/v3"
    DOUBAO_MODEL: str = ""

    LOG_LEVEL: str = "INFO"
    DB_PATH: str = "runtime/data/gomoku.db"

    @field_validator("DEFAULT_LLM")
    @classmethod
    def _check_default_llm(cls, v: str) -> str:
        v = v.strip().lower()
        if v not in PROVIDERS:
            raise ValueError(f"DEFAULT_LLM 必须是 {PROVIDERS} 之一，当前: {v}")
        return v

    @property
    def configured_providers(self) -> list[str]:
        """已配置 API Key 的模型列表。"""
        return [p for p in PROVIDERS if getattr(self, f"{p.upper()}_API_KEY")]

    @model_validator(mode="after")
    def _fallback_default_llm(self) -> Settings:
        """默认模型未配置 Key 时回退到第一个已配置模型。

        一个 Key 都没配也允许：此时没有可用解说模型，仅剩本地对弈与建议。
        """
        if self.configured_providers and self.DEFAULT_LLM not in self.configured_providers:
            self.DEFAULT_LLM = self.configured_providers[0]
        return self

    def provider_config(self, name: str) -> dict[str, str]:
        """取某家模型的 (api_key, base_url, model) 配置。"""
        name = name.strip().lower()
        if name not in PROVIDERS:
            raise ConfigError(f"未知模型: {name}")
        return {
            "api_key": getattr(self, f"{name.upper()}_API_KEY"),
            "base_url": getattr(self, f"{name.upper()}_BASE_URL"),
            "model": getattr(self, f"{name.upper()}_MODEL"),
        }


def _default_env_file() -> str:
    """默认 .env 位置：优先 exe/项目根同级，其次当前工作目录。"""
    from app.common.paths import _base_dir

    beside_app = _base_dir() / ".env"
    if beside_app.exists():
        return str(beside_app)
    return ".env"


def load_settings(env_file: str | Path | None = None) -> Settings:
    """加载配置；校验失败统一转为 ConfigError。"""
    try:
        if env_file is not None:
            return Settings(_env_file=str(env_file))  # type: ignore[call-arg]
        return Settings(_env_file=_default_env_file())  # type: ignore[call-arg]
    except Exception as exc:
        raise ConfigError(f"配置加载失败: {exc}") from exc

"""模型注册表：集中管理四家模型配置，新增模型只改一处。"""

from __future__ import annotations

import logging

from app.common.errors import ConfigError
from app.llm.openai_compat import OpenAICompatClient
from app.settings import PROVIDERS, Settings

logger = logging.getLogger(__name__)

# 各家展示名（UI 下拉用）
DISPLAY_NAMES: dict[str, str] = {
    "deepseek": "DeepSeek",
    "kimi": "Kimi",
    "glm": "GLM",
    "doubao": "豆包",
}


class LLMRegistry:
    """按名称注册/取用 LLM 客户端；只注册已配置 Key 的模型。"""

    def __init__(self, settings: Settings) -> None:
        self._clients: dict[str, OpenAICompatClient] = {}
        for name in PROVIDERS:
            cfg = settings.provider_config(name)
            if not cfg["api_key"]:
                continue
            if not cfg["model"]:
                logger.warning("模型 %s 已配置 Key 但未配置模型名，跳过注册", name)
                continue
            self._clients[name] = OpenAICompatClient(
                name=name,
                display_name=DISPLAY_NAMES.get(name, name),
                api_key=cfg["api_key"],
                base_url=cfg["base_url"],
                model=cfg["model"],
            )
        if self._clients:
            logger.info("LLM 注册完成: %s", ", ".join(self._clients))
        else:
            # 不配置 Key 也允许启动：仅本地对弈与建议，不做 LLM 解说
            logger.warning("未配置任何 LLM 模型（*_API_KEY），本次运行不进行 AI 解说")

    @property
    def default_name(self) -> str:
        """第一个可用模型；一个都没配置时返回空串。"""
        return next(iter(self._clients), "")

    @property
    def available(self) -> list[str]:
        return list(self._clients)

    def display_name(self, name: str) -> str:
        return DISPLAY_NAMES.get(name, name)

    def get(self, name: str) -> OpenAICompatClient:
        if name not in self._clients:
            raise ConfigError(f"模型未配置或不存在: {name}")
        return self._clients[name]

"""OpenAI 兼容实现：四家（DeepSeek/豆包/Kimi/GLM）统一走 openai SDK。"""

from __future__ import annotations

import logging
from collections.abc import Iterator

from openai import OpenAI

logger = logging.getLogger(__name__)

REQUEST_TIMEOUT = 60.0
MAX_TOKENS = 800


class OpenAICompatClient:
    """stream_commentary 以生成器逐块回传文本。"""

    def __init__(
        self,
        name: str,
        display_name: str,
        api_key: str,
        base_url: str,
        model: str,
        temperature: float = 0.3,
    ) -> None:
        self.name = name
        self.display_name = display_name
        self.model = model
        self.temperature = temperature
        self._client = OpenAI(api_key=api_key, base_url=base_url, timeout=REQUEST_TIMEOUT)

    def stream_commentary(self, prompt: str) -> Iterator[str]:
        """流式请求；异常向上抛，由 commentary_service 经 fallback 处理。"""
        logger.debug("LLM 请求: model=%s prompt_len=%d (Key 已脱敏)", self.model, len(prompt))
        stream = self._client.chat.completions.create(
            model=self.model,
            messages=[
                {"role": "system", "content": SYSTEM_MESSAGE},
                {"role": "user", "content": prompt},
            ],
            temperature=self.temperature,
            max_tokens=MAX_TOKENS,
            stream=True,
        )
        for chunk in stream:
            if not chunk.choices:
                continue
            delta = chunk.choices[0].delta
            text = getattr(delta, "content", None)
            if text:
                yield text


SYSTEM_MESSAGE = (
    "你是一位亲切的五子棋解说。用简洁的中文口语解说，"
    "按用户要求的要点分段，每段一到三句话，适合在侧边栏阅读。"
    "不要输出 Markdown 标记与棋盘图，直接给自然语言。"
    "你只负责分析局面，落子建议由程序另行给出，不要在回复中给出推荐落点。"
)

"""LLM 客户端抽象接口。"""

from __future__ import annotations

from collections.abc import Iterator
from typing import Protocol


class LLMClient(Protocol):
    """流式解说客户端协议：四家 OpenAI 兼容实现共用。"""

    name: str

    def stream_commentary(self, prompt: str) -> Iterator[str]:
        """流式生成解说文本块；失败由调用方经 fallback 处理。"""
        ...

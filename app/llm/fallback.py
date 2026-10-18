"""LLM 失败降级：返回标准文案"解说不可用"，对局继续。"""

from __future__ import annotations

import logging

logger = logging.getLogger(__name__)

FALLBACK_TEXT = "（解说不可用：网络或模型服务暂时异常，对局不受影响，可继续落子。）"


def fallback_text(reason: BaseException) -> str:
    """异常 → 降级文案；记 WARNING 日志（不含 Key 等敏感信息）。"""
    logger.warning("LLM 解说失败，已降级: %s: %s", type(reason).__name__, reason)
    return FALLBACK_TEXT

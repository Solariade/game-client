"""统一错误类型：区分领域异常与基础设施异常。"""

from __future__ import annotations


class AppError(Exception):
    """应用统一异常基类。"""


class DomainError(AppError):
    """领域层异常（非法落子等规则违反）。"""


class InfrastructureError(AppError):
    """基础设施异常（DB / LLM / 文件等外部依赖故障）。"""


class LLMError(InfrastructureError):
    """LLM 调用失败（网络、鉴权、限流、超时等）。"""


class ConfigError(InfrastructureError):
    """配置缺失或非法。"""

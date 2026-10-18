"""资源与运行时路径统一定位。

资源外置策略：
- 打包后：优先从 exe 同级 ``assets/`` 读取；
- 开发期：回退到项目根 ``assets/``；
- 不提供内嵌兜底——分发时必须连同 ``assets/`` 目录一起拷贝。
全项目禁止硬编码路径，统一经过本模块。
"""

from __future__ import annotations

import sys
from pathlib import Path


def _base_dir() -> Path:
    """打包后：exe 所在目录；开发期：项目根目录。"""
    if getattr(sys, "frozen", False):
        return Path(sys.executable).parent
    return Path(__file__).resolve().parents[2]


def asset(*parts: str) -> Path:
    """资源统一从 exe 同级 assets/ 读取；开发期回退项目根 assets/。"""
    return _base_dir() / "assets" / Path(*parts)


def runtime_dir(*parts: str) -> Path:
    """运行时目录（log/data/cache），不存在时自动创建。"""
    p = _base_dir() / "runtime" / Path(*parts)
    p.mkdir(parents=True, exist_ok=True)
    return p

"""registry 与 paths 单测。"""

from __future__ import annotations

from pathlib import Path

import pytest

from app.common.errors import ConfigError
from app.common.paths import _base_dir, asset, runtime_dir
from app.llm.registry import DISPLAY_NAMES, LLMRegistry
from app.settings import Settings


def make_settings(**kw) -> Settings:
    # _env_file=None：测试不读项目根的真实 .env
    return Settings(_env_file=None, **kw)  # type: ignore[call-arg]


class TestLLMRegistry:
    def test_registers_only_configured(self) -> None:
        s = make_settings(GLM_API_KEY="k", GLM_MODEL="m", KIMI_API_KEY="k2", KIMI_MODEL="m2")
        reg = LLMRegistry(s)
        assert reg.available == ["kimi", "glm"]
        assert reg.default_name == "kimi"

    def test_skips_provider_without_model_name(self) -> None:
        """豆包只配 Key 未配模型名 → 被跳过，注册表为空但不报错。"""
        s = make_settings(DOUBAO_API_KEY="k")  # 无 DOUBAO_MODEL
        reg = LLMRegistry(s)
        assert reg.available == []
        assert reg.default_name == ""

    def test_no_keys_allowed(self) -> None:
        """一个 Key 都不配也能构造注册表：仅本地对弈与建议。"""
        reg = LLMRegistry(make_settings(GLM_MODEL="m"))
        assert reg.available == []
        assert reg.default_name == ""

    def test_get_and_display(self) -> None:
        s = make_settings(GLM_API_KEY="k", GLM_MODEL="m")
        reg = LLMRegistry(s)
        assert reg.get("glm").model == "m"
        assert reg.display_name("glm") == "GLM"
        assert DISPLAY_NAMES["deepseek"] == "DeepSeek"

    def test_get_unknown_raises(self) -> None:
        s = make_settings(GLM_API_KEY="k", GLM_MODEL="m")
        with pytest.raises(ConfigError):
            LLMRegistry(s).get("deepseek")


class TestPaths:
    def test_dev_base_dir_is_project_root(self) -> None:
        assert _base_dir().name == "game-client"
        assert (_base_dir() / "pyproject.toml").exists()

    def test_asset_path(self) -> None:
        p = asset("logo.png")
        assert p.parent.name == "assets"
        assert p.name == "logo.png"

    def test_frozen_base_dir_uses_executable(self, monkeypatch: pytest.MonkeyPatch) -> None:
        fake_exe = Path("D:/somewhere/app.exe")
        monkeypatch.setattr("sys.frozen", True, raising=False)
        monkeypatch.setattr("sys.executable", str(fake_exe))
        assert _base_dir() == Path("D:/somewhere")

    def test_runtime_dir_creates(self, tmp_path, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setattr("app.common.paths._base_dir", lambda: tmp_path)
        p = runtime_dir("data")
        assert p.exists() and p.is_dir()

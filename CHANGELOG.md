# 更新日志

本项目遵循 [Keep a Changelog](https://keepachangelog.com/zh-CN/1.1.0/)，
版本号遵循 [语义化版本](https://semver.org/lang/zh-CN/)。

## [Unreleased]

## [1.0.0] - 2026-10-18

### 新增

- 15×15 五子棋对局，本地 Minimax + Alpha-Beta 引擎，四档难度（搜索深度 2~5）；
- DeepSeek / Kimi / GLM / 豆包四家模型接入，统一 OpenAI 兼容接口与流式解说；
- 本地落子建议：引擎按当前难度 +1 层搜索，支持虚拟棋子预选与确认；
- 两次点击落子：预选可改选，Esc / 右键取消；
- 对局、落子与解说持久化到 SQLite，日志按天轮转；
- LLM 网络、鉴权、限流异常时降级为「解说不可用」，不影响对局；
- 无 API Key 也可完整对弈与使用落子建议。

### 打包与工程

- PyInstaller 目录模式打包，产物目录带版本号，自动清理旧产物；
- 打包自动生成 Windows 版本信息，并附带 README、LICENSE、使用说明与 VERSION.txt；
- 分发用 `.env` 由 `.env.example` 生成，不含真实 Key；
- 提供 ruff、mypy、pytest、pre-commit 与 GitHub Actions CI；
- 采用 MIT License 开源。

[Unreleased]: https://github.com/Solariade/game-client/compare/v1.0.0...HEAD
[1.0.0]: https://github.com/Solariade/game-client/releases/tag/v1.0.0

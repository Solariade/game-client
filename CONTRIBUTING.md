# 贡献指南

感谢你愿意为 game-client 做出贡献。本文说明本地开发、检查与提交 Pull Request 的流程。

## 环境准备

- Windows 10 / 11
- Python 3.12
- [uv](https://docs.astral.sh/uv/)

```powershell
git clone git@github.com:Solariade/game-client.git
cd game-client
uv sync
uv run pre-commit install
```

LLM 解说为可选功能。需要联调时，复制 `.env.example` 为 `.env` 并填入自己的 Key；
**不要提交 `.env` 或任何真实 Key**。

## 提交前检查

```powershell
uv run ruff check .
uv run ruff format --check .
uv run mypy app
uv run pytest
```

四项必须全部通过。也可以直接运行：

```powershell
uv run pre-commit run --all-files
```

## 代码约定

- 依赖方向为 `ui → services → (core, ai, llm, db)`，`core` 不依赖上层；
- 新增或修改行为时请补充测试，测试放在 `tests/unit/` 或 `tests/integration/`；
- 遵循现有代码风格，公开函数与模块添加简短中文 docstring；
- 不要提交 `runtime/`、`build/`、`dist/`、`.venv/` 等本地产物。

更详细的架构与开发说明见 [架构说明](docs/architecture.md) 与 [开发规范](docs/development.md)。

## 提交信息

采用 [Conventional Commits](https://www.conventionalcommits.org/zh-hans/) 格式：

```
<type>: <简短说明>
```

常用 `type`：`feat`、`fix`、`docs`、`test`、`refactor`、`chore`、`build`、`ci`。

## Pull Request

1. 从 `master` 拉出功能分支；
2. 保持改动聚焦，避免混入无关的格式化或重构；
3. 在 PR 描述中说明动机、改动内容与验证方式；
4. 确认 CI 全部通过。

## 安全问题

请勿公开提交安全漏洞，报告方式见 [安全策略](SECURITY.md)。

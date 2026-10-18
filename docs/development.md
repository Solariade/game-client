# 开发规范

## 环境与命令

```powershell
uv sync                          # 安装依赖（含 dev 组）
uv run python -m app             # 启动应用
uv run pytest                    # 测试
uv run pytest --cov=app          # 覆盖率（当前基线约 65%，新增代码请补测试）
uv run ruff check app tests      # lint
uv run ruff format app tests     # 格式化
uv run mypy app                  # 类型检查
uv run python build.py           # 打包（目录模式，自动清理）
```

仅 Windows 环境支持打包；不提供 .sh 脚本，统一 README + build.py。

## 提交规范

- 分支：`main`（稳定）/ `feature/*` / `fix/*`；
- pre-commit（ruff + ruff-format + 尾随空格）通过后才可提交；
- 提交信息：`<type>: <摘要>`，type ∈ feat / fix / refactor / test / docs / chore。

## 代码约定

- 领域层 `app/core/` 禁止导入任何外部依赖（仅标准库 + `common/errors`）；
- 全项目禁止硬编码路径，统一 `common/paths.py` 的 `asset()` / `runtime_dir()`；
- 后台线程不得直接操作 Tkinter 控件，一律 queue + after 回主线程；
- 日志禁止打印 API Key 与完整请求体（脱敏后再记）；
- 新增模型只改 `settings.py`（环境变量）与 `llm/registry.py`（展示名）；
- 错误分两层：`DomainError`（规则违反）/ `InfrastructureError`（外部依赖）。

## 测试约定

- `tests/unit/`：纯函数与领域规则（棋盘、评估、引擎、提示词、服务编排）；
- `tests/integration/`：仓储（临时 SQLite 文件）、LLM 客户端（respx 拦截，不打真实 API）；
- 涉及外部服务的测试必须 mock；引擎测试关注行为（必胜/必挡）而非具体分值。

## 打包与分发

- `build.py` 固定目录模式且打包前自动清理；`assets/` 外置与 exe 同级，不内嵌；
- 版本号取自 `pyproject.toml`，同时写入 exe 版本信息；产物目录为 `dist/game-client-v<version>/`；
- 分发必须连同 `assets/` 目录；`runtime/` 首次运行自动创建；
- spec 文件生成在 `build/` 临时目录，不维护、不入库；
- 分发包附带 `.env`、`.env.example`、`README.md`、`LICENSE`、`使用说明.txt` 与 `VERSION.txt`；
- 产物中的 `.env` 由 `.env.example` 生成，不含真实 API Key，可安全分发。

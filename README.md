<p align="center">
  <img src="assets/logo256.png" width="120" alt="game-client logo">
</p>

<h1 align="center">game-client · 五子棋与象棋 AI 对弈</h1>

<p align="center">
  Windows 桌面双棋种 · 本地引擎走棋 · 多家 LLM 流式解说
</p>

![game-client 界面](assets/screenshot.png)

## 功能特性

- **双棋种对弈**：五子棋（内置 Minimax + Alpha-Beta 引擎）与象棋
  （外部 Pikafish 引擎，四档难度对应不同思考时长），「棋种」下拉即切
- **象棋完整体验**：选子高亮全部合法落点（可吃子用红环标注）、可选虚拟棋子
  （二次点击确认，默认关闭）、最后一手与建议的起终点标记、被将军红环警示、
  中文记法（炮二平五）、引擎评分展示、将死/困毙判定并高亮输方将/帅
- **悔棋**：「悔棋」按钮或 Ctrl+Z 撤销一回合，终局后也可悔棋续弈（棋谱与
  数据库结果同步回退）
- **多家模型解说**：DeepSeek / Kimi / GLM / 豆包，统一 OpenAI 兼容接口，流式输出；
  象棋解说额外附引擎评估与主要变例
- **本地落子建议**：引擎按当前难度更高一档搜索，不依赖模型，也不会给出非法着法
- **无 Key 也能玩**：不配置任何 API Key 时，对局、难度与落子建议全部可用
- **对局持久化**：SQLite 保存对局、落子与解说（象棋着法存 ICCS），日志按天轮转
- **失败降级**：LLM 异常仅显示「解说不可用」；Pikafish 未安装时隐藏象棋入口，
  五子棋不受影响

## 系统要求

- Windows 10 / 11
- Python 3.12
- [uv](https://docs.astral.sh/uv/)（推荐）或 pip
- 象棋模式需另装 [Pikafish](docs/pikafish-setup.md)（可选，免费开源）

## 快速开始

```powershell
# 0. 克隆仓库
git clone git@github.com:Solariade/game-client.git
cd game-client

# 1. 安装依赖
uv sync

# 2. 配置模型 Key（可选；不填也能下棋，只是没有 AI 解说）
copy .env.example .env

# 3. 启动
uv run python -m app

# 4.（可选）安装象棋引擎：见 docs/pikafish-setup.md
#    下载 Pikafish 放入 assets/engines/ 即可启用象棋
```

## 配置模型（可选）

编辑 `.env`，填入任意一家或多家模型的 Key：

| 模型 | API Key 变量 | 默认模型 | Base URL |
|---|---|---|---|
| DeepSeek | `DEEPSEEK_API_KEY` | `deepseek-chat` | `https://api.deepseek.com` |
| Kimi | `KIMI_API_KEY` | `moonshot-v1-8k` | `https://api.moonshot.cn/v1` |
| GLM | `GLM_API_KEY` | `glm-4-flash` | `https://open.bigmodel.cn/api/paas/v4` |
| 豆包 | `DOUBAO_API_KEY` | 接入点 ID（`ep-xxxx`） | `https://ark.cn-beijing.volces.com/api/v3` |

- `DEFAULT_LLM`：默认解说模型，可选 `deepseek` / `kimi` / `glm` / `doubao`；
- `XIANGQI_ENGINE_PATH`：象棋引擎路径，留空使用 `assets/engines/pikafish.exe`；
- `XIANGQI_VIRTUAL_PIECE`：象棋虚拟棋子，`true` 时点落点先预览、再次点击确认，
  默认 `false`（点落点直接走子）；
- `DB_PATH`：对局数据库路径，默认 `runtime/data/game.db`（五子棋与象棋共用）；
- 豆包的 `DOUBAO_MODEL` 需填写方舟接入点 ID；
- Key 只保存在本机 `.env` 中，已被 `.gitignore` 忽略，不会上传或打包外泄。

更多说明见 [LLM 接入说明](docs/llm-integration.md)。

## 使用

- **五子棋**：你执黑先行，两次点击交叉点落子（第一次预选可改选，Esc / 右键取消）；
- **象棋**：右侧「棋种」切换；执黑时棋盘自动翻转，己方棋子始终在下方；
  点己方棋子选中并显示合法落点（空位绿点、可吃子红环），点标记直接走子；
  设置 `XIANGQI_VIRTUAL_PIECE=true` 后改为先放虚拟棋子、再点一次确认，
  Esc / 右键先取消虚拟棋子、再按取消选子；被将军时己方将/帅显示红环；
- 绿色标记是本地引擎的建议（象棋会同时标出起点与终点），不依赖大模型；
- **悔棋**：点击「悔棋」或按 Ctrl+Z，撤销到重新轮到你；AI 思考中不可悔棋；
- 专家模式思考较久（五子棋约 8~15 秒，象棋约 3 秒）；配置模型后每步流式解说一次；
- 对局数据保存在 `runtime/data/game.db`（两棋种共用），日志位于 `runtime/log/app.log`；
- 完整操作说明见 [使用说明](docs/使用说明.txt)。

## 项目结构

```
app/
├── core/        领域层：棋盘、规则、棋种抽象（含象棋规则内核，纯标准库）
├── ai/          引擎层：五子棋 Minimax + α-β；象棋 Pikafish UCI 封装
├── llm/         模型接入：OpenAI 兼容客户端、双棋种提示词、注册表、降级
├── services/    编排层：轮次状态机、棋种规格、解说流水线
├── ui/          Tkinter 界面：双棋盘画布、分析面板、设置与状态栏
├── db/          SQLite 持久化：建表即用
└── common/      路径、日志、线程、错误等横切工具
```

依赖方向：`ui → services → (core, ai, llm, db)`，`core` 不依赖上层。详见 [架构说明](docs/architecture.md)。

## 开发与测试

```powershell
uv run pytest                 # 测试（301 项）
uv run pytest --cov=app       # 覆盖率
uv run ruff check .           # lint
uv run ruff format --check .  # 格式检查
uv run mypy app               # 类型检查
```

提交前请安装并运行 pre-commit：

```powershell
uv run pre-commit install
uv run pre-commit run --all-files
```

开发规范、代码约定与提交信息格式见 [开发规范](docs/development.md)。

## 打包

```powershell
uv run python build.py
```

默认目录模式，自动清理旧产物，输出 `dist/game-client-v<version>/`。版本号取自 `pyproject.toml` 并写入 exe 版本信息；产物中的 `.env` 由 `.env.example` 生成，不含真实 Key。

```
dist/game-client-v1.1.0/
├── game-client.exe
├── assets/               # 图标资源；engines/ 视本地是否装有 Pikafish
├── _internal/            # PyInstaller 运行时
├── .env / .env.example
├── README.md / LICENSE
├── VERSION.txt
└── 使用说明.txt
```

`runtime/` 由程序首次运行自动创建。分发时拷贝整个版本目录即可。

**引擎与许可**：本地装有 Pikafish 时会随包拷贝并在 `assets/engines/`
附 GPL-3.0 许可说明（再分发须遵守 GPL-3.0）；未安装时产物放置下载指引，
象棋模式自动禁用。详见 [Pikafish 安装指引](docs/pikafish-setup.md)。

## 文档

- [文档索引](docs/README.md)
- [架构说明](docs/architecture.md)
- [开发规范](docs/development.md)
- [LLM 接入说明](docs/llm-integration.md)
- [象棋开发方案](docs/xiangqi-plan.md)
- [Pikafish 安装指引](docs/pikafish-setup.md)
- [归档：完整开发方案](docs/archive/development-plan.md)
- [更新日志](CHANGELOG.md)

## 贡献

欢迎提交 Issue 与 Pull Request。开始前请阅读 [贡献指南](CONTRIBUTING.md) 与
[开发规范](docs/development.md)，并确保 `ruff`、`mypy`、`pytest` 全部通过。

安全漏洞请按 [安全策略](SECURITY.md) 私下报告，不要公开提交 Issue。

## License

[MIT](LICENSE) © 2026 [Solariade](https://github.com/Solariade)

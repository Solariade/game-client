# game-client · 五子棋 AI 对弈学习 Windows 桌面应用 · 完整开发方案

> **归档文档**：本文是项目初期的完整开发方案，保留用于追溯设计决策。
> 当前架构与实现请以 [架构说明](../architecture.md) 为准。

> 版本：v1.2（按最新确认调整）  
> 技术栈：Python 3.12 / uv / Tkinter / SQLite / 多 LLM（DeepSeek、豆包、Kimi、GLM）

---

## 一、项目概述

### 1.1 目标

开发一款 **Windows 10 桌面五子棋应用**（项目名 `game-client`），用户与 AI 对弈。AI 由两部分组成：

- **本地搜索引擎**：负责走棋决策（Minimax + Alpha-Beta 剪枝），保证棋力与响应速度；
- **LLM 解说层**：负责拆招解招、预判后续几步，以自然语言输出到棋盘右侧面板。

默认**用户先走**，每走一步后 AI 落子并生成解说。架构为**后期扩展象棋**预留空间。

### 1.2 需求确认结果

| 需求项 | 决策 |
|---|---|
| 项目名 | `game-client` |
| 棋种 | 首版仅五子棋（15×15）；架构支持后期增加象棋 |
| 先手 | 用户先走 |
| AI 走棋 | 本地引擎计算，不依赖 LLM |
| AI 解说 | **每一步**都调用 LLM，拆招 + 预判后续 2~3 步 |
| 模型 | DeepSeek、豆包、Kimi、GLM 四家（忽略元宝） |
| LLM 失败 | 右侧面板显示"解说不可用"，不中断对局 |
| 难度 | 用户可选搜索深度（简单/中等/困难/专家） |
| 打包 | 全部逻辑写在 `build.py`，**不维护独立 spec 文件** |
| 打包默认 | **固定目录模式**（启动更快、便于替换资源），打包前自动清理 |
| 资源策略 | **`assets/` 与 exe 同级**，外置可直接替换；不采用内嵌兜底 |
| 脚本 | 仅 Windows 环境，**不提供 .sh 脚本** |
| 数据库迁移 | **不做迁移设计**，首版建表即用，后续需要时再明确 |
| 资源现状 | 仅有 `logo.ico`、`logo.png`；**无棋盘背景图**，首版 Canvas 绘制棋盘 |

### 1.3 核心设计原则

1. **走棋与解说分离**：LLM 不决定落子，只解释局面；落子以本地引擎为准。
2. **分层解耦**：领域规则 / 引擎 / LLM / 服务编排 / UI / 持久化各自独立。
3. **棋种可扩展**：抽象基类隔离五子棋与象棋差异，新增棋种不改服务层与 UI 框架。
4. **降级可用**：LLM 不可用时对局照常进行。
5. **线程安全**：AI 搜索与 LLM 流式接收在后台线程，UI 更新回主线程。
6. **路径统一管理**：禁止硬编码，资源与运行时目录由 `paths.py` 统一定位。

---

## 二、技术栈

| 类别 | 选型 |
|---|---|
| 语言 | Python ≥ 3.12 |
| 包管理 | uv（`pyproject.toml` + `uv.lock`） |
| GUI | Tkinter（标准库）+ Canvas |
| 数据库 | SQLite（标准库 `sqlite3`），**建表即用，无迁移框架** |
| LLM 调用 | `openai` SDK（OpenAI 兼容接口） |
| 配置管理 | `pydantic-settings` + `python-dotenv` |
| 日志 | 标准库 `logging` + 轮转 Handler |
| 测试 | pytest + pytest-cov + mock/respx |
| 静态检查 | ruff（lint + format）、mypy |
| 提交钩子 | pre-commit |
| 打包 | PyInstaller，**由 `build.py` 编程调用，目录模式，资源外置** |

---

## 三、目录结构

```
game-client/
├── pyproject.toml                  # uv 项目配置、依赖、工具链
├── uv.lock
├── README.md
├── LICENSE
├── build.py                        # 打包入口：PyInstaller 编程接口，目录模式，资源外置
├── .env.example                    # 环境变量模板（不含真实 Key）
├── .env                            # 本地真实配置（gitignore）
├── .gitignore
├── .python-version
├── .pre-commit-config.yaml
│
├── app/                            # 应用主体：入口 + 全部业务模块
│   ├── __init__.py
│   ├── __main__.py                 # 支持 python -m app 启动
│   ├── main.py                     # 程序入口：装配依赖、启动 UI
│   ├── bootstrap.py                # 初始化：配置、日志、DB、LLM 客户端
│   ├── settings.py                 # 配置加载与校验
│   │
│   ├── core/                       # 领域层：纯规则，无外部依赖
│   │   ├── __init__.py
│   │   ├── base_game.py            # 棋种抽象基类（为象棋预留）
│   │   ├── constants.py            # 通用常量（棋色、方向、棋型）
│   │   ├── exceptions.py           # 领域异常
│   │   └── gomoku/
│   │       ├── __init__.py
│   │       ├── board.py            # 五子棋棋盘状态、落子、胜负判定
│   │       └── rules.py            # 五子棋规则细节
│   │
│   ├── ai/                         # 本地引擎层（按棋种隔离）
│   │   ├── __init__.py
│   │   ├── base_engine.py          # 引擎抽象基类（为象棋预留）
│   │   ├── difficulty.py           # 难度→深度映射
│   │   └── gomoku/
│   │       ├── __init__.py
│   │       ├── engine.py           # Minimax + Alpha-Beta 主流程
│   │       ├── evaluator.py        # 棋型评估函数
│   │       └── move_ordering.py    # 候选走法生成/排序
│   │
│   ├── llm/                        # LLM 接入层（与棋种无关）
│   │   ├── __init__.py
│   │   ├── base.py                 # LLMClient 抽象接口
│   │   ├── openai_compat.py        # OpenAI 兼容实现
│   │   ├── registry.py             # 模型注册表（名称→配置）
│   │   ├── prompts.py              # 提示词模板（按棋种分模板）
│   │   └── fallback.py             # 失败降级
│   │
│   ├── services/                   # 应用服务层（编排，棋种无关）
│   │   ├── __init__.py
│   │   ├── game_service.py         # 轮次管理、用户/AI 走棋编排
│   │   └── commentary_service.py   # 局面→提示词→LLM→解说
│   │
│   ├── ui/                         # 表现层（Tkinter）
│   │   ├── __init__.py
│   │   ├── main_window.py          # 主窗口布局
│   │   ├── analysis_panel.py       # 右侧解说面板（流式追加）
│   │   ├── controls.py             # 模型/难度/棋种选择等控件
│   │   ├── theme.py                # 颜色、字体等样式常量
│   │   └── boards/                 # 各棋种棋盘渲染（为象棋预留）
│   │       ├── __init__.py
│   │       ├── base_board_canvas.py # 棋盘画布抽象基类
│   │       └── gomoku_canvas.py     # 五子棋棋盘绘制与点击
│   │
│   ├── db/                         # 持久层（SQLite，建表即用）
│   │   ├── __init__.py
│   │   ├── connection.py           # 连接管理
│   │   ├── schema.sql              # 建表 DDL
│   │   └── repositories.py         # games/moves 仓储
│   │
│   └── common/                     # 通用工具
│       ├── __init__.py
│       ├── logging.py              # 日志配置（输出到 runtime/log）
│       ├── paths.py                # 资源/运行时路径统一定位
│       ├── errors.py               # 统一错误类型
│       └── threading_utils.py      # 后台任务/线程安全回调
│
├── assets/                         # 静态资源（与 exe 同级，外置）
│   ├── logo.ico                    # 窗口/任务栏/exe 图标
│   ├── logo.png                    # 标题区/关于页 Logo
│   └── images/                     # 预留：后续可放棋盘背景图
│       └── .gitkeep
│
├── tests/
│   ├── __init__.py
│   ├── conftest.py
│   ├── unit/
│   │   ├── test_gomoku_board.py
│   │   ├── test_evaluator.py
│   │   └── test_prompts.py
│   ├── integration/
│   │   ├── test_llm_client.py
│   │   └── test_repositories.py
│   └── fixtures/
│
├── runtime/                        # 运行时产物（gitignore，保留 .gitkeep）
│   ├── log/
│   │   └── .gitkeep
│   ├── data/
│   │   └── .gitkeep
│   └── cache/
│       └── .gitkeep
│
└── docs/
    ├── architecture.md
    ├── llm-integration.md
    └── development.md
```

### 3.1 关键调整说明

#### 打包形态与资源策略（对应本轮确认 1、2）

- `build.py` **固定目录模式**（onedir），每次打包前自动清理 `build/` 与 `dist/`。
- 版本号取自 `pyproject.toml`，并写入 Windows exe 的版本信息；产物目录带版本号。
- **资源外置**：`assets/` 不打进 exe 内部，而是**与 exe 同级**放置。打包后目录形如：

```
dist/game-client-v1.0.0/
├── game-client.exe
├── assets/
│   ├── logo.ico
│   ├── logo.png
│   └── images/
├── _internal/...          # PyInstaller 运行时依赖
├── .env                  # 由 .env.example 生成，不含真实 Key
├── .env.example
├── README.md
├── LICENSE
├── VERSION.txt
└── 使用说明.txt
```

- 优点：用户可直接替换 `assets/logo.png` 或后续放入 `assets/images/board_bg.png` 生效，无需重新打包。
- 代价：分发时必须拷贝整个版本目录（含 `assets/`），README 需明确说明。
- 产物中的 `.env` 由 `.env.example` 生成，不含真实 API Key，可安全分发；程序优先读取 exe 同级的 `.env`。
- `paths.py` 的资源定位规则相应调整为：**优先 exe 同级 `assets/`**；开发期回退到项目根 `assets/`。**不做内嵌兜底**。

#### 数据库简化（对应本轮确认 3）

- 移除 `migrations.py` 与 `schema_version` 表；
- 首版 `connection.py` 在连接时执行 `schema.sql`（全部 `CREATE TABLE IF NOT EXISTS`），**建表即用**；
- 后续若需要版本化迁移，再单独提出并补 `migrations.py`。

#### 棋种扩展设计（沿用）

| 层 | 扩展方式 |
|---|---|
| `core/` | `base_game.py` 定义 `BaseGame` 抽象类；五子棋在 `core/gomoku/`，象棋后续新增 `core/xiangqi/` |
| `ai/` | `base_engine.py` 定义 `BaseEngine`；五子棋在 `ai/gomoku/`，象棋后续新增 `ai/xiangqi/` |
| `ui/boards/` | `base_board_canvas.py` 定义画布抽象；五子棋在 `gomoku_canvas.py`，象棋后续新增 `xiangqi_canvas.py` |
| `llm/prompts.py` | 按棋种分模板（`GOMOKU_PROMPT`、未来的 `XIANGQI_PROMPT`） |
| `services/` | 完全棋种无关，注入 `BaseGame` / `BaseEngine` 实例 |
| `db/` | `games.game_type` 字段区分棋种，表结构不变 |
| `controls.py` | 预留棋种选择控件（首版仅五子棋） |

#### 脚本（沿用）

- **不提供** `.sh` 脚本；开发命令写在 `README`；
- 打包统一由 `build.py` 承担。

#### 资源现状（对应本轮确认）

- 现有：`assets/logo.ico`、`assets/logo.png`；
- **无棋盘背景图**：首版 Canvas 绘制——木色底 + 网格线 + 星位 + 坐标标注；
- `assets/images/` 保留占位，后续放入背景图后仅改 `gomoku_canvas.py` 绘制分支，无需改打包逻辑。

---

## 四、模块设计

### 4.1 配置层 `app/settings.py`

用 `pydantic-settings` 从 `.env` 加载并校验：

```env
# .env.example
DEFAULT_LLM=deepseek

DEEPSEEK_API_KEY=
DEEPSEEK_BASE_URL=https://api.deepseek.com
DEEPSEEK_MODEL=deepseek-chat

KIMI_API_KEY=
KIMI_BASE_URL=https://api.moonshot.cn/v1
KIMI_MODEL=moonshot-v1-8k

GLM_API_KEY=
GLM_BASE_URL=https://open.bigmodel.cn/api/paas/v4
GLM_MODEL=glm-4-flash

DOUBAO_API_KEY=
DOUBAO_BASE_URL=https://ark.cn-beijing.volces.com/api/v3
DOUBAO_MODEL=<endpoint-id>

LOG_LEVEL=INFO
DB_PATH=runtime/data/gomoku.db
```

- 模型 Key 可选：不配置任何 Key 也能启动，此时只有本地 AI 对弈与本地落子建议，不进行 LLM 解说。
- 配置了多个模型时，`DEFAULT_LLM` 未配置 Key 会回退到第一个已配置的模型。
- 真实 Key 只放 `.env`，`.env.example` 提供模板。
- 日志中禁止打印 Key，请求体日志需脱敏。

### 4.2 领域层 `app/core/`

**`base_game.py`**：抽象基类

```python
class BaseGame(ABC):
    @abstractmethod
    def place(self, move: Move, color: int) -> None: ...
    @abstractmethod
    def undo(self) -> Move: ...
    @abstractmethod
    def check_win(self, move: Move) -> bool: ...
    @abstractmethod
    def is_full(self) -> bool: ...
    @abstractmethod
    def clone(self) -> "BaseGame": ...
    @abstractmethod
    def to_text(self) -> str: ...          # 供 LLM 提示词使用
```

**`core/gomoku/board.py`**：15×15 二维数组（0 空 / 1 黑 / -1 白），实现 `BaseGame`：
- `place(row, col, color)`：落子并校验合法性；
- `undo()`：撤销（供搜索回溯）；
- `check_win(row, col)`：从落子点向四方向统计连续同色数；
- `is_full()`、`clone()`、`to_text()`。

**`core/gomoku/rules.py`**：胜负判定等规则细节（首版可不用禁手）。

**`constants.py`**：棋色、方向向量、棋型枚举。

**`exceptions.py`**：`IllegalMoveError` 等领域异常。

领域层无外部依赖，可独立单测。

### 4.3 本地引擎 `app/ai/`

**`base_engine.py`**：`BaseEngine.search(game: BaseGame, depth: int) -> Move`。

**`difficulty.py`**：难度→深度映射（棋种无关的档位定义）。

**`ai/gomoku/evaluator.py`**：按棋型加权评分——五连极高、活四、冲四、活三、眠三依次递减；AI 与用户分值取差。

**`ai/gomoku/move_ordering.py`**：
- 候选点仅取已有棋子周围 2 格内空位，大幅降低分支因子；
- 按启发式分值排序，提升剪枝效率。

**`ai/gomoku/engine.py`**：Minimax + Alpha-Beta 剪枝主流程，实现 `BaseEngine`。

| 难度 | 深度 | 预期思考时间 |
|---|---|---|
| 简单 | 2 | < 0.3 s |
| 中等（默认） | 3 | 0.5~1 s |
| 困难 | 4 | 1.5~5 s |
| 专家 | 5 | 7~15 s（可能较慢） |

> Alpha-Beta 剪枝可将 3 层搜索从约 11 秒降至 0.5 秒左右；专家模式若实测超 15 秒，可在 UI 标注"思考时间较长"。

> 叶子节点除静态评估外，还会检查“轮走方能否一步成五”：静态棋型分不区分先后手，
> 双方各有一个四时容易误判成均势，缺少这一步会走出自己冲四、却被对手先成五的漏着。

### 4.4 LLM 接入层 `app/llm/`

**`base.py`**：抽象接口

```python
class LLMClient(Protocol):
    def stream_commentary(self, prompt: str) -> Iterator[str]: ...
```

**`registry.py`**：集中管理四家模型配置（名称、base_url、model、默认参数）。新增模型只改一处。

**`openai_compat.py`**：四家均提供或兼容 OpenAI 接口：

```python
client = OpenAI(base_url=cfg.base_url, api_key=cfg.api_key)
```

**`prompts.py`**：按棋种分模板。五子棋提示词包含：
1. 棋种与当前局面（文本化棋盘，黑=1/白=2/空=0）；
2. 用户刚走的位置、AI 准备走的位置；
3. 任务：拆解用户意图、解释 AI 攻防理由、预判后续 2~3 步；
4. 输出格式约束：简洁分段，适合侧边栏展示。

**`fallback.py`**：捕获超时、鉴权失败、限流等异常，返回标准文案"解说不可用"，记 `WARNING` 日志，对局继续。

**流式输出**：`stream=True`，逐字回传，UI 侧边栏实时追加。

### 4.5 服务编排 `app/services/`

**`game_service.py`**：核心流程编排（棋种无关，注入 `BaseGame` / `BaseEngine`）

```
用户落子 → 校验 → 更新棋盘 → 禁用输入
  → 后台线程：engine.search(game, depth) → 得到 AI 走法
  → AI 落子 → 触发 commentary_service
  → 恢复用户输入
```

- 状态标志 `ai_thinking` 控制，思考期间棋盘点击忽略；
- 每步写入 `moves` 表。

**`commentary_service.py`**：

```
局面 + 双方走法 → prompts 组装（按棋种选模板）
  → LLMClient.stream_commentary()
  → 逐块经 queue 回主线程 → analysis_panel 追加
  → 异常 → fallback 文案
```

> AI 落子与 LLM 解说可不同步——先落子让用户看到，再流式显示解说。

### 4.6 UI 层 `app/ui/`

**布局**：水平分割

```
┌──────────────────────────────┬─────────────────────────┐
│                              │  棋种: [五子棋 ▼]        │
│                              │  模型: [DeepSeek ▼]      │
│                              │  难度: [中等 ▼]          │
│      棋盘 Canvas             │  ─────────────────────  │
│   （Canvas 绘制木色底+网格）  │  AI 分析：               │
│                              │  “你这一步…”             │
│                              │  “我走这里是因为…”       │
│                              │  “预判接下来…”           │
│                              │  ─────────────────────  │
│                              │  控制按钮 / 历史记录     │
└──────────────────────────────┴─────────────────────────┘
```

**`boards/base_board_canvas.py`**：抽象基类，定义 `draw()`、`pixel_to_grid()`、`on_click` 回调契约。

**`boards/gomoku_canvas.py`**：
- 首版无背景图，Canvas 绘制：木色矩形底、15×15 网格线、五个星位圆点、坐标标注（A~O / 1~15）；
- 棋子用 `create_oval` 绘制；
- 点击事件将像素坐标转为棋盘坐标；落子采用两次点击（先画双圈 + 中心点的虚拟子，再点同一子确认），
  第一次点击后可改选其它空位，Esc / 右键取消；
- 引擎建议落子用「绿色虚线光环 + 缩小的建议棋子」标注，与用户预选虚拟子区分；
- 预留 `self._bg_img` 属性，后续接入背景图时 `PhotoImage` 存于此防 GC。

**`main_window.py`**：
- `root.iconbitmap(default=str(asset("logo.ico")))` 设置窗口图标（Windows）；
- `root.iconphoto(...)` 用 `logo.png` 兼容其他平台；
- Logo 用于标题区或"关于"对话框。

**`analysis_panel.py`**：流式文本追加，自动滚动。

**`controls.py`**：棋种下拉（首版仅五子棋）、模型下拉、难度下拉、重开/复盘按钮。

**线程安全**：后台线程通过 `queue.Queue` + `root.after()` 把结果送回主线程，禁止在子线程直接操作控件。

### 4.7 持久层 `app/db/`（建表即用，无迁移）

**`schema.sql`**：

```sql
CREATE TABLE IF NOT EXISTS games (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    game_type TEXT NOT NULL,           -- 'gomoku' / 未来 'xiangqi'
    model_name TEXT,
    difficulty TEXT,
    user_color TEXT NOT NULL,
    result TEXT DEFAULT 'ongoing',
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS moves (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    game_id INTEGER NOT NULL REFERENCES games(id),
    move_number INTEGER NOT NULL,
    player TEXT NOT NULL,              -- 'user' / 'ai'
    position TEXT NOT NULL,            -- 'row,col'
    llm_commentary TEXT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);
```

- `connection.py` 连接时执行 `schema.sql`（全部 `IF NOT EXISTS`），首版建表即用；
- **不引入** `migrations.py` / `schema_version`；后续需要时再补；
- `repositories.py`：`GameRepository`、`MoveRepository`，封装增查；
- DB 路径来自 `settings`，默认 `runtime/data/gomoku.db`。

### 4.8 通用工具 `app/common/`

**`paths.py`**：资源与运行时路径统一定位（**资源外置策略**）

```python
import sys
from pathlib import Path

def _base_dir() -> Path:
    """打包后：exe 所在目录；开发期：项目根目录。"""
    if getattr(sys, "frozen", False):
        return Path(sys.executable).parent
    return Path(__file__).resolve().parents[2]

def asset(*parts: str) -> Path:
    """资源统一从 exe 同级 assets/ 读取；开发期回退项目根 assets/。
    不提供内嵌兜底——分发时必须带上 assets/ 目录。"""
    return _base_dir() / "assets" / Path(*parts)

def runtime_dir(*parts: str) -> Path:
    p = _base_dir() / "runtime" / Path(*parts)
    p.mkdir(parents=True, exist_ok=True)
    return p
```

> **关键约束**：`assets/` 与 `runtime/` 均基于 exe 同级目录定位；打包时 `assets/` 不打进 exe，由 `build.py` 拷贝到输出目录。全项目禁止硬编码路径。

**`logging.py`**：`setup_logging()` 输出到 `runtime/log/`，用 `TimedRotatingFileHandler` 按天轮转（如 `app-2026-10-17.log`）。分级：
- `DEBUG`：搜索节点数、LLM 请求体（脱敏）；
- `INFO`：对局开始/结束、模型切换；
- `WARNING`：LLM 超时降级；
- `ERROR`：未捕获异常。

**`threading_utils.py`**：后台任务封装、线程安全回调。

**`errors.py`**：统一错误类型，区分领域异常与基础设施异常。

---

## 五、启动流程

```
uv run python -m app
  → settings 加载 .env（Key 可选，缺失时仅本地对弈）
  → setup_logging() 写 runtime/log/
  → 打开 runtime/data/gomoku.db，执行 schema.sql（建表即用）
  → 构建 LLM registry（只注册已配置 Key 的模型）
  → 启动 Tkinter 主窗口
      → 用户选难度/模型，落子
      → game_service 触发 AI：后台线程按深度搜索
      → AI 落子后 commentary_service 流式调 LLM
      → 流式文本经 queue 回主线程，追加到右侧面板
      → 每步写入 moves 表
```

开发期统一用 `uv run python -m app`（依赖 `app/__main__.py`），避免 `sys.path` 问题。

---

## 六、打包方案：`build.py`

### 6.1 设计要点

- **不维护 spec 文件**，全部逻辑在根目录 `build.py`；
- 通过 PyInstaller Python 编程接口 `PyInstaller.__main__.run` 驱动；
- **固定目录模式**（`--onedir`），不提供单文件模式；
- **打包前自动清理** `build/` 与 `dist/`；
- **资源外置**：`--add-data` 不把 `assets/` 打进 exe，打包完成后由 `build.py` 将 `assets/` 拷贝到输出目录（与 exe 同级）；
- **版本信息**：从 `pyproject.toml` 读取版本号，生成 `VSVersionInfo` 并通过 `--version-file` 写入 exe；
- **产物带版本号**：输出到 `dist/game-client-v<version>/`，可并存多个版本；
- **配置与文档随包**：由 `.env.example` 生成 `.env`，并拷贝 `.env.example`、`README.md`、`LICENSE`、`使用说明.txt`，生成 `VERSION.txt`；产物不含真实 Key；
- 图标使用 `assets/logo.ico`；
- GUI 程序 `--windowed`。

### 6.2 `build.py` 结构（示意）

- `read_version()`：从 `pyproject.toml` 的 `[project].version` 读取版本号；
- `write_version_file()`：生成 `build/game-client.txt`（`VSVersionInfo`，UTF-8 BOM），供 `--version-file` 使用；
- `finalize_output()`：把 PyInstaller 默认产物整理为带版本号的目录，并调用 `copy_assets_to()` 与 `copy_extra_files()`；
- `copy_extra_files()`：由 `.env.example` 生成 `.env`，并拷贝 `.env.example`、`README.md`、`LICENSE`、`使用说明.txt`，生成 `VERSION.txt`；
- 打包逻辑集中在 `main()`。

```python
def read_version() -> str:
    data = tomllib.loads((ROOT / "pyproject.toml").read_text(encoding="utf-8"))
    return str(data["project"]["version"])


def write_version_file(path: Path, version: str) -> None:
    """生成 PyInstaller VSVersionInfo；中文内容需 UTF-8 BOM。"""
    ...


def finalize_output(out_dir: Path, version: str) -> None:
    """把默认产物整理成 dist/game-client-v<version>/。"""
    if out_dir.exists():
        shutil.rmtree(out_dir)
    (DIST / APP_NAME).rename(out_dir)
    copy_assets_to(out_dir)
    copy_extra_files(out_dir, version)  # .env / 文档 / 许可证 / VERSION.txt


def main() -> int:
    clean()  # 每次打包前自动清理
    version = read_version()
    version_file = BUILD / f"{APP_NAME}.txt"
    write_version_file(version_file, version)

    PyInstaller.__main__.run([
        str(ENTRY),
        "--name", APP_NAME,
        "--onedir",
        "--windowed",
        "--icon", str(ICON),
        "--version-file", str(version_file),
        # schema.sql 是运行时读取的数据文件，必须显式打包
        "--add-data", f"{ROOT / 'app' / 'db' / 'schema.sql'};app/db",
        # 注意：assets 不用 --add-data，由 finalize_output 外置拷贝
        ...
    ])

    finalize_output(DIST / f"{APP_NAME}-v{version}", version)
    return 0
```

完整实现见根目录 `build.py`。

### 6.3 使用方式

```powershell
uv sync
uv run python build.py                  # 目录模式，自动清理
```

### 6.4 打包产物形态

```
dist/game-client-v1.0.0/
├── game-client.exe       # 已写入版本信息
├── assets/               # 外置，可直接替换
│   ├── logo.ico
│   ├── logo.png
│   └── images/
├── _internal/...
├── .env                  # 由 .env.example 生成，不含真实 Key
├── .env.example
├── README.md
├── LICENSE
├── VERSION.txt           # 版本、构建时间、Python/PyInstaller 版本
├── 使用说明.txt
└── runtime/              # 首次运行自动创建
    ├── log/
    └── data/
```

> 版本号来自 `pyproject.toml`（当前 `1.0.0`）；程序优先读取 exe 同级的 `.env`。

> 产物中的 `.env` 由 `.env.example` 生成，不含真实 Key，可安全分发；使用者填写后即可启用 AI 解说。

> 分发时拷贝**整个版本目录**即可；`runtime/` 由程序首次运行自动创建。

### 6.5 依赖

`pyproject.toml` 的 dev 组：

```toml
[dependency-groups]
dev = [
    "pytest>=8.0", "pytest-cov>=5.0",
    "ruff>=0.6", "mypy>=1.11", "pre-commit>=3.8",
    "pyinstaller>=6.6",
]
```

---

## 七、静态资源规范

| 资源 | 路径 | 说明 |
|---|---|---|
| 应用图标 | `assets/logo.ico` | 已存在；窗口/任务栏/exe 图标 |
| Logo | `assets/logo.png` | 已存在；标题区/关于页 |
| 棋盘背景 | `assets/images/`（预留） | **首版无**，Canvas 绘制；后续放入图片即可，无需改打包 |
| 字体 | `assets/fonts/`（预留） | 可选 |

约定：
- 加载图片必须保持引用（存实例属性），防 Tkinter GC；
- `assets/` 纳入版本库并随 exe 外置分发；`runtime/` 忽略（保留 `.gitkeep`）；
- 资源查找统一走 `paths.asset()`，**无内嵌兜底**。

---

## 八、企业级工程规范

### 8.1 依赖与工具

- `uv` 管理依赖，`uv.lock` 提交入库；
- `ruff` 统一 lint + format，`mypy` 类型检查；
- `pre-commit` 挂 ruff、mypy、尾随空格检查。

### 8.2 配置与密钥

- 真实 Key 只放 `.env`；`.env.example` 模板化；
- `settings.py` 启动即校验必填项；
- 模型注册表集中管理，新增模型只改一处；
- 日志脱敏，禁止打印 Key。

### 8.3 错误处理

- 领域异常与基础设施异常分开定义；
- LLM 调用统一捕获异常，`fallback.py` 返回"解说不可用"并记 `WARNING`；
- UI 层只处理面向用户的提示。

### 8.4 测试策略

- **unit/**：五子棋规则、评估函数、提示词拼接——纯函数易测；
- **integration/**：LLM 客户端用 mock/respx 录制响应，不打真实 API；仓储层用临时 SQLite 文件；
- `pytest-cov` 设覆盖率门槛（核心模块 ≥ 70%）。

### 8.5 线程与 UI 安全

- AI 搜索与 LLM 流式接收在后台线程；
- 结果经 `queue.Queue` + `root.after()` 回主线程；
- 思考期间 `ai_thinking` 标志阻止棋盘点击。

### 8.6 版本与协作

- 分支：`main`（稳定）+ `feature/*` + `fix/*`；
- `pre-commit` 保证提交质量；
- `docs/` 维护架构、LLM 接入、开发规范；
- `README` 保持"5 分钟跑起来"最小说明 + 打包命令 + **资源需随 exe 分发**说明。

---

## 九、开发里程碑建议

| 阶段 | 内容 |
|---|---|
| M1 | 项目骨架、配置、日志、paths（外置资源定位）、SQLite 建表 |
| M2 | 五子棋领域层 + 单测（落子、胜负、克隆、to_text） |
| M3 | 本地引擎（评估、走法排序、Minimax+剪枝）+ 单测 |
| M4 | Tkinter 主窗口、Canvas 绘制棋盘、点击落子、轮次控制 |
| M5 | LLM 四家接入、流式解说、降级、右侧面板 |
| M6 | 难度选择、模型选择、落子与解说联动打磨 |
| M7 | 对局入库、复盘基础能力 |
| M8 | `build.py` 打包验证（默认 onedir + 资源外置 + 图标/Logo 生效） |
| M9 | 文档、README、pre-commit、覆盖率收尾 |

---

## 十、遗留风险与提示

1. **资源外置的分发要求**：用户必须同时拿到 `game-client.exe`（或目录）与 `assets/`，否则启动时图标/Logo 缺失。README 与打包输出提示中需明确。
2. **专家模式耗时**：深度 5 在 Python 中可能 8~15 秒，建议 UI 上标注，必要时封顶 4 层。
3. **每步调用 LLM 的成本**：一局约 20~40 次 API 调用，需在 README 提示用户注意用量；流式输出保证等待体验。
4. **无迁移的演进**：后续若改表结构，需手工处理旧库（删除或补列），届时再引入迁移方案。

方案已按本轮三项确认完成调整，可直接作为开发依据。如需继续，我可以产出：`app/common/paths.py` 完整实现、`gomoku_canvas.py` 绘制结构、`ai/gomoku/engine.py` 搜索主流程骨架、`build.py` 完整可运行版本。
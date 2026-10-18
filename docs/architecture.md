# 架构说明

## 分层

```
app/
├── core/        领域层：纯规则（无外部依赖，可独立单测）
├── ai/          引擎层：Minimax + Alpha-Beta（按棋种隔离）
├── llm/         LLM 接入层：四家 OpenAI 兼容 + 流式 + 降级
├── services/    编排层：轮次状态机、解说流水线（棋种无关）
├── ui/          表现层：Tkinter，线程安全（queue + after）
├── db/          持久层：SQLite 建表即用
└── common/      路径/日志/线程/错误等横切工具
```

依赖方向：`ui → services → (core, ai, llm, db)`；`core` 不依赖任何上层。

## 关键设计

### 走棋与解说分离
LLM 不决定落子，只解释局面。落子一律以本地引擎 `GomokuEngine.search()` 为准，
解说经 `CommentaryService` 异步流式生成，失败降级为固定文案，对局不受影响。

### 棋种扩展点
- `core/base_game.py` 的 `BaseGame` 抽象；
- `ai/base_engine.py` 的 `BaseEngine`；
- `ui/boards/base_board_canvas.py` 的 `BaseBoardCanvas`；
- `llm/prompts.py` 按棋种分模板；
- services 层注入实例，不改代码；
- `games.game_type` 字段区分棋种。

新增象棋 = 新建 `core/xiangqi/`、`ai/xiangqi/`、`ui/boards/xiangqi_canvas.py`、
`XIANGQI_PROMPT`，注册到 controls 棋种下拉。

### 线程模型
- 用户点击、所有 UI 更新：主线程；
- AI 搜索、LLM 流式接收：后台守护线程（`common/threading_utils.run_in_background`）；
- 跨线程只通过 `queue.Queue`，主线程 `QueuePoller` 以 `root.after` 轮询消费；
- `ai_thinking` 标志期间棋盘点击被忽略。

### 路径策略（资源外置）
`common/paths.py`：打包后定位到 exe 同级目录，开发期为项目根。
`assets/` 与 `runtime/` 都基于该目录；分发时 `assets/` 必须随 exe 一起拷贝。
无内嵌兜底——缺资源时图标/Logo 缺失但程序可运行。

### 引擎要点
- 候选点：已有棋子周围 2 格内空位，限宽取前 20，按"进攻+防守"启发分排序；
- 快速路径：己方一步成五直接走；对方一步成五直接挡；
- 胜负分带剩余深度奖励：优先更快的胜利；
- 难度 → 深度：简单 2 / 中等 3 / 困难 4 / 专家 5。

## 数据模型

见 `app/db/schema.sql`：`games`（对局元数据）与 `moves`（逐步记录 + 解说回填）。
建表即用（全部 `CREATE TABLE IF NOT EXISTS`），无迁移框架。

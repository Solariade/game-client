# 象棋开发方案

> 状态：M10–M15 全部完成（2026-10-19），v1.1.0 已打包验证；
> M16 界面与体验优化完成（2026-10-19）
> 关联：[架构说明](architecture.md) · [开发规范](development.md) · [归档：五子棋开发方案](archive/development-plan.md)
> 需求来源：象棋架构方案（阅后即焚，已并入本文档）

---

## 一、背景与目标

在现有 game-client（五子棋 AI 对弈 + LLM 解说）架构上，新增**中国象棋**棋种，
功能与五子棋完全对齐：人机对弈、四档难度、本地落子建议、LLM 流式解说、
SQLite 持久化、PyInstaller 打包。

核心思路：**复用项目已预留的棋种扩展点**（`BaseGame` / `BaseEngine` /
`BaseBoardCanvas` / 提示词分模板 / `games.game_type`），不新建工程、不改服务层框架。

## 二、需求决策

| 需求项 | 决策 | 说明 |
|---|---|---|
| 走棋引擎 | **外部 Pikafish（UCI 子进程）** | 不自写强搜索引擎；Python 只做进程通信 |
| 规则校验 | **手写纯标准库 `core/xiangqi/`** | 零依赖、可独立单测、支撑 UI 合法点位提示；不引入第三方规则库（API 漂移风险） |
| 引擎缺失时 | **提示并禁用象棋** | 启动探测 `assets/engines/`，缺失则棋种下拉置灰 + 面板给出下载指引；不内置兜底引擎（进 Backlog） |
| 功能范围 | **与五子棋完全对齐** | 人机、四档难度、本地建议、LLM 解说、持久化、打包 |
| 解说输入 | FEN + 引擎评分 + 主要变例（PV） | 比五子棋多喂引擎信息，降低模型幻觉 |
| 难度 | 四档沿用 简单/中等/困难/专家 | 映射为引擎思考时长（movetime），见 5.2 |
| 持久化 | 共用现有库表 | `game_type='xiangqi'`，`position` 存 ICCS 着法（如 `h2e2`），schema 不变 |
| LLM | 复用四家 OpenAI 兼容接入与降级 | 仅新增 `XIANGQI_PROMPT` |

## 三、总体架构

各职责在现有分层中的落位：

```
职责                          →  落位
UCI 子进程通信                 →  app/ai/xiangqi/uci.py
Pikafish 引擎封装              →  app/ai/xiangqi/engine.py
象棋规则（棋盘/走法/FEN/记法）   →  app/core/xiangqi/（board/rules/fen/notation）
解说生成                      →  复用 app/llm/ + services/commentary_service.py
棋盘画布                      →  app/ui/boards/xiangqi_canvas.py
主窗口与棋种切换               →  复用 app/ui/main_window.py
引擎路径等配置                 →  app/settings.py
```

```
┌──────────────────────────────────────────────┐
│ ui（Tkinter）主线程：棋盘交互 / 面板 / 状态栏    │
│   GomokuCanvas ⇄ XiangqiBoardCanvas 可切换    │
└──────────────┬───────────────────────────────┘
┌──────────────▼───────────────────────────────┐
│ services（棋种参数化注入）                      │
│   GameService 轮次状态机 │ CommentaryService   │
└───────┬──────────────────────┬───────────────┘
        │                      │
┌───────▼────────┐   ┌─────────▼──────────────┐
│ ai/xiangqi      │   │ llm（OpenAI 兼容 ×4）    │
│ UCI 子进程封装   │   │ 流式解说 + 失败降级       │
│ Pikafish + NNUE │   └────────────────────────┘
└───────┬────────┘
┌───────▼──────────────────────────────────────┐
│ core/xiangqi：纯规则（走法/将军/将死/FEN/记法）  │
└──────────────────────────────────────────────┘
```

关键原则不变：**走棋与解说分离**——LLM 不决定走子；象棋走子一律以 Pikafish 为准，
本地规则层只做用户点击的即时合法性校验与 UI 交互；解说异步流式、失败降级。

## 四、关键设计

### 4.1 颜色与先手映射

沿用 `Color` 的整数语义：**红 = 1（先手）、黑 = -1**，与五子棋 黑=1 先手完全同构。
`GameService.user_turn` 的奇偶推断逻辑（`moves_count % 2`）零改动复用。

- DB `user_color` 存 `'red'` / `'black'`；
- 象棋模式下设置区「执黑」文案显示为「执红」（值仍为 1 / -1，见 5.5）。

### 4.2 Move 数据结构扩展

象棋着法是「起点 → 终点」，现有 `Move(row, col)` 只有单点。扩展为：

```python
@dataclass(frozen=True)
class Move:
    row: int                # 起点
    col: int
    to_row: int | None = None   # 象棋终点；五子棋恒为 None
    to_col: int | None = None
```

- 五子棋全部代码路径不感知新字段，行为不变；
- `BaseGame.place(move, color)` 签名不变：象棋实现从 move 中取起终点；
- ICCS 坐标（`h2e2`）与 `Move` 的互转放 `core/xiangqi/fen.py`。

### 4.3 引擎并发与生命周期

- **单引擎实例 + `threading.Lock`**：AI 回合线程（走子）与建议线程共用一个
  Pikafish 进程，命令串行化，避免 UCI 交错（线程安全要求）；
- **惰性启动**：首次 `search()` 才拉起子进程，纯五子棋用户不付出启动开销；
- **崩溃恢复**：读写线程检测到进程退出 → 重新拉起一次 → 仍失败抛
  `EngineError`，UI 显示「引擎出错，可重新开局」（复用 `ai_error` 事件路径）；
- **退出清理**：应用退出时发送 `quit` 并 `wait(timeout=3)`，超时 `kill`
  （`main.py` 退出路径统一处理）；
- **hash 复用**：每回合只发 `position fen …` + `go`，仅新对局时 `ucinewgame`
  （每次 bestmove 都 `ucinewgame` 会白白丢置换表）。

### 4.4 降级矩阵

| 故障 | 表现 | 对对局影响 |
|---|---|---|
| Pikafish 未安装 | 象棋项在下拉中置灰，面板提示下载方法 | 无（五子棋不受影响） |
| 引擎进程崩溃 | 自动重启一次；失败则提示引擎出错 | 本局可重新开局恢复 |
| 引擎超时无 bestmove | 抛 `EngineError` → `ai_error` 事件 | 同上 |
| LLM 失败 | 复用现有 fallback：面板「解说不可用」 | 无 |
| Tk 不可用（CI） | 现有跳过逻辑覆盖新 UI 测试 | 无 |

### 4.5 服务层参数化（小重构，已实施）

`GameService` 不再硬编码 `GomokuBoard` 与 `game_type='gomoku'`，改为注入
`GameSpec`（`app/services/game_spec.py`，`make_gomoku_spec()` / `make_xiangqi_spec()`）：

```python
@dataclass(frozen=True)
class GameSpec:
    """一个棋种的全部注入点。"""
    game_type: str                    # 'gomoku' / 'xiangqi'
    game_factory: Callable[[], BaseGame]
    user_color_name: Callable[[int], str]     # 1→'black'/'red' …
    position_text: Callable[[Move], str]      # Move→'r,c' 或 'h2e2'
    color_display: Callable[[int], str]       # 状态栏「黑/白」或「红/黑」
```

与原设计的差异（实现时决定）：
- **engine 不进 GameSpec**，仍作为 `GameService` 的独立注入参数——两个引擎共用
  `BaseEngine` 接口，且这样旧构造用法（`engine=`）零改动；
- `BaseGame` 新增抽象 `is_playable(move)` 与 `moves_count`、具体 `win_line()`
  （缺省 None，象棋无连线概念）：`suggest_for_user()` 用 `is_playable` 过滤，
  五子棋实现 = 界内空位，象棋实现 = 己方子起手且该着合法；
- `CommentaryService.generate(client, prompt, ...)` 只收 prompt 字符串，
  组装在 UI 主线程完成（失败时不开流式段，面板不会卡在 streaming）；
- `GameService.play_user_move(move)` 承接象棋「起点→终点」着法，
  `user_move(row, col)` 保留为五子棋便捷入口。

五子棋回归要求（已满足）：现有测试**不改断言**全绿，仅调整了
`add_move`（收 `position: str`）与 `generate`（收 prompt）两处调用参数。

## 五、模块设计

### 5.1 `core/xiangqi/`（纯标准库）

| 文件 | 职责 |
|---|---|
| `board.py` | `XiangqiBoard(BaseGame)`：10 行×9 列，格子存 FEN 字符（大写红 `RNBAKCP` / 小写黑 `/空串`）；`place`（合法性校验 + 吃子历史）、`undo`（恢复被吃子）、`valid_moves`（含将军过滤）、`clone`、`to_text`（LLM 文本局面）、`is_playable` |
| `rules.py` | 七兵种**伪走法**生成（车马炮相仕兵将）：蹩马腿、塞象眼、相不过河、仕帅限九宫、兵过河横走、将帅对脸禁着；`is_in_check`；伪走法→合法走法过滤（走后己方不被将军） |
| `fen.py` | FEN 解析/生成（标准象棋 FEN，含 `w/b` 行棋方）；ICCS `h2e2` ↔ `Move` 互转 |
| `notation.py` | 中文着法记法（炮二平五 / 马8进7），红黑各按己方视角纵线；供面板与提示词显示 |

胜负判定：

- `winner`：一方**无任何合法走法**时判定——被将军 = 将死（负），未被将军 = 困毙（象棋规则同样判负）；
- `check_win(move)`：该着走完后对方无合法走法即为 True；
- `is_full()` 恒 `False`（接口兼容，象棋无满盘平局）；
- 长将/长捉禁着规则首版不实现（Backlog），对局中遇到概率低且判定复杂。

### 5.2 `ai/xiangqi/`

**`uci.py` — UCIProcess（子进程封装）：**

- `Popen` + `text=True, bufsize=1` + `CREATE_NO_WINDOW`（Windows 不弹黑框）；
- 后台读者线程持续读 stdout 入 `queue.Queue`；
- `send(cmd)` / `_wait_for(token, timeout)`：`uciok` / `readyok` / `bestmove` 同步等待，超时抛 `UCITimeoutError`；
- 启动握手：`uci` → 等待 `uciok`（记录 options，供探测 `UCI_LimitStrength` 等）→ `setoption EvalFile`（NNUE 与 exe 同目录时）→ `isready`；
- 读者线程发现流关闭（进程退出）→ 置崩溃标志并唤醒等待者。

**`engine.py` — XiangqiEngine(BaseEngine)：**

```python
class XiangqiEngine(BaseEngine):
    def search(self, game, depth, ai_color=None) -> Move:
        """depth 复用为难度档索引；内部映射为 movetime，
        position fen + go movetime → bestmove ICCS → Move。"""

    def analyze(self, game, movetime_ms: int) -> EngineEval:
        """返回 (bestmove, score_cp, pv[iccs...])；供解说与本地建议共用。"""

    def available(self) -> bool: ...   # 探测引擎文件是否存在（不启动进程）
```

- 引擎发现顺序：`Settings.XIANGQI_ENGINE_PATH` > `assets/engines/pikafish.exe`；
  均无 → `EngineUnavailableError`（启动探测用，不会走到走棋阶段）；
- `score mate N` 解析为 `EngineEval.mate_in`（带符号步数：正 = 红方 N 步杀、负 = 黑方），供面板显示「X 步内将死」；
- **难度映射**（`engine.py` 的 `DEPTH_TO_MOVETIME_MS`，`depth` 参数即档位；
  建议着法取上一档并封顶 3000 ms，由服务层 `get(depth + 1, 3000)` 实现）：

| 难度 | movetime | 建议 movetime | 备注 |
|---|---|---|---|
| 简单 | 300 ms | 800 ms | 若握手报告支持 `UCI_LimitStrength/UCI_Elo`，可再压低棋力（实现时以引擎实际 options 为准，不硬编码） |
| 中等 | 800 ms | 1500 ms | |
| 困难 | 1500 ms | 3000 ms | |
| 专家 | 3000 ms | 3000 ms | 思考体验对齐五子棋专家档（8~15 秒以内） |

- 走法信任：引擎返回的 ICCS 走子前仍过一遍 `place()` 校验（双保险，异常按 `ai_error` 处理）。

### 5.3 `llm/prompts.py` — XIANGQI_PROMPT

在 `GOMOKU_PROMPT` 旁新增模板，输入比五子棋多引擎客观信息：

```
你正在解说一局中国象棋（红先）。
局面 FEN：{fen}
着法记录（中文记法）：{move_history}
刚才用户（{user_color_name}）走 {user_move}，AI（{ai_color_name}）走 {ai_move}。
引擎评估：{score_text}（正数红优、负数黑优）；主要变例：{pv_text}
```

解说要求沿用三段式（用户意图 / AI 着法理由 / 预判），总长 ≤150 字、
不输出棋盘图与走子建议（建议由程序本地给出）。

实现补充（M13 已落地）：
- `XiangqiEngine.last_eval` 记录最近一次 analyze 结果（与 search 同锁同线程，
  `take_ai_turn` 在 search 后立即读取），`TurnResult.engine_eval` 由此填充；
- `XiangqiBoard.history_notations()` 从起始 FEN 重演生成中文记法序列
  （记住 `_start_fen`，clone 一并复制）；PV 的中文记法在提示词内重演转换，
  遇非法着法截断（取前 6 步）；
- `score_display(eval)` 生成评分文案：mate → 「红方/黑方 N 步内可将死」，
  否则「红方视角 ±N 厘兵」；`_on_ai_move` 检测到 mate 时面板即时提示；
- `_start_commentary` 按棋盘类型（isinstance XiangqiBoard/GomokuBoard）选
  prompt 组装函数，未知类型按解说不可用降级。

### 5.4 `ui/boards/xiangqi_canvas.py`

- 基类 `BaseBoardCanvas` 假定正方形棋盘，象棋是 **9 列 × 10 行**：
  基类构造增加可选 `rows: int | None = None`（缺省等于 `board_size`），向后兼容；
- 绘制：木色底、9×10 交叉线、**楚河汉界**（中间两行竖线断开、题字）、
  九宫斜线、炮/兵位折角标记、外侧坐标（红方汉字一~九、黑方数字 1~9）；
- 棋子：圆形棋子 + 汉字（红：帅仕相马车炮兵 / 黑：将士象马车炮卒），
  选中棋子高亮环，最后一着起/终点标记；
- 交互：
  1. 点**己方棋子** → 选中，画出该子**全部合法落点**（本地规则即时计算）；
  2. 点**合法终点** → 默认直接走子；开启 `XIANGQI_VIRTUAL_PIECE=true` 后
     先画**虚拟棋子**（吃子时外圈红环）且不改变棋局，点其它合法终点可移动
     虚拟棋子，再点同一虚拟棋子才真正走子；
  3. 点其它己方子 → 改选；Esc / 右键取消（虚拟棋子开启时先取消虚拟棋子、
     选子保留，再按一次取消选子）；
- `sync_board` 全量重绘（象棋仅 32 子，性能无虞）；
- 终局：将死/困毙时高亮输方将/帅，状态栏文案说明取胜原因。

### 5.5 `ui/` 棋种切换

- `controls.py`：棋种下拉启用 `["五子棋", "象棋"]`；
  引擎不可用时象棋项置灰（Tk Combobox 无逐项禁用，用「象棋(未安装引擎)」
  占位文案 + 选中时提示实现）；「执黑」标签按棋种显示「执黑」/「执红」；
- `main_window.py`：切换棋种 = 用对应 `GameSpec` 重建 `GameService`、
  `canvas.destroy()` 后按棋种新建画布、清空面板重开一局；
  **AI 思考中禁止切换**（与重新开局同策略）；
- `bootstrap.py`：启动时探测 Pikafish 可用性（只查文件存在，不拉进程），
  组装 `GameSpec` 注册表 `{game_type: spec}`；`AppContext` 暴露给 UI。

实现补充（M14 已落地）：

- 引擎缺失的降级比上文设想更直接：**下拉里不出现「象棋」项**
  （`GameServiceFactory.available_games()` 过滤，bootstrap 记 warning 日志），
  `_on_game_change` 仍保留不可用守卫（回退下拉 + 面板提示），不再需要占位文案；
- 注册表落在 `services/game_spec.py` 的 `GameServiceFactory`
  （集中持有两棋种引擎 + specs + 仓库，`create(game_type, user_color)` 重建服务、
  `shutdown()` 退出前关引擎子进程、`available_games()` 探测可玩棋种）；
  `AppContext.game_factory` 暴露，`MainWindow` 新增可选参数 `service_factory`
  （None 时保持旧行为：仅五子棋、下拉禁用，旧测试不受影响）；
- 切换时 **config 随迁**（难度/模型/建议开关）与 user_color 保持；
  画布经 `_build_canvas()` 重建并重绑 `<Button-3>`（Esc 是 root 级绑定无需重绑）；
- 选子状态 `MainWindow._xq_selection` 由主窗口持有，画布只负责
  `show_selection / clear_selection` 渲染（光环 + 落点，空位绿点/敌子绿环）；
- 关窗走 `WM_DELETE_WINDOW → _on_close → factory.shutdown()`，
  确保 Pikafish 子进程随主程序退出（冒烟已验证 tasklist 无残留）；
- 象棋建议：`show_hint` 画起点虚线环 + 终点标记，面板给中文记法
  （`notation.move_text`），选子期间不画（避免与落点标记混叠）。

验收后修复（2026-10-19，用户反馈三项）：

- 棋盘靠右：切换棋种重建画布时按入列顺序排到了右侧面板之后——
  改为 `_build_layout` 先建右面板、画布恒经 `_pack_canvas()` 以
  `pack(before=side_panel)` 插前（`pack_slaves()` 顺序有回归测试）；
- 定位错乱：`draw()` 曾把 `_grid_xy` 返回的 `(x, y)` 中 x 解包给 y 轴
  （纵线坍缩成点、外框压扁），已重写为按轴显式解包，并新增
  `TestBoardGeometry` 几何回归（边线全高、纵线河界断开、外框/河界题字/
  纵线号坐标逐一断言）；
- 默认棋种：`GameServiceFactory.default_game`（象棋优先、引擎缺失回落
  五子棋），bootstrap 据此建首局，控件下拉 `set_game` 同步；
  另棋盘在画布大于棋盘时自动居中（`<Configure>` 触发整盘重放）。

### 5.7 第二轮界面与体验优化（M16，2026-10-19）

| 项 | 改动 |
|---|---|
| 启动执子文案 | 以象棋启动时执子格误取 `game_options[0]`（五子棋）→ 显示「我执黑」；现同时调用 `set_game + apply_game + set_user_color`，显示「我执红」 |
| 棋盘视觉 | `cell` 40→46、`margin` 34→56，顶部数字/底部汉字纵线号不再被首末行棋子遮挡；棋子增加传统内圈描边 |
| 棋子字号 | 汉字改用像素字号（负值，避免 DPI 放大），按字宽+ascent 的外接矩形自适应并留 6% 余量；实测 cell=46 取 20px（原 21pt≈28px），字不压内圈且不过小 |
| 切换重绘 | 切换棋种时新画布只画了棋盘底，象棋棋子不显示；现在重建画布后立即 `_sync_canvas()` 按新对局重绘（含来回切换回归测试） |
| 执子视角 | 执黑时棋盘旋转 180°（逻辑坐标经 `_grid_xy` 翻转，骨架用 `_screen_xy` 不参与变换），黑方在下方、纵线号切换为 9~1；换边后 `set_flipped` 原地重绘并保留覆盖层 |
| 落点语义 | 空位绿点、**可吃敌子红环**（`theme.CAPTURE_RING`）、选子蓝环、建议绿环四者区分 |
| 覆盖层重放 | 画布缓存选子/建议/将军/终局状态；`<Configure>` 整盘重放后自动恢复（此前会全部消失） |
| 将军提示 | 行棋方被将军时其将/帅套红环（`CHECK_TAG`），状态栏与 AI 思考文案标注「将军！」 |
| 悔棋 | `GameService.undo_round()`：正常对局撤销一回合两步，终局后只撤销致胜一步；同步删除 `moves` 记录、`games.result` 恢复 `ongoing`；UI 提供「悔棋」按钮与 Ctrl+Z |
| 评估与记谱 | AI 每步后显示一行短评分（`score_brief`）；状态栏显示上一手中文记法；象棋读秒文案改为「行棋」 |

测试：新增 24 项（覆盖层重放、吃子色、悔棋编排与持久化、启动文案），
全仓 286 项通过；`ruff` / `mypy` 通过。

### 5.8 象棋虚拟棋子（M17，2026-10-19）

- **可选功能，默认关闭**：`Settings.XIANGQI_VIRTUAL_PIECE`（`.env` 键
  `XIANGQI_VIRTUAL_PIECE`）为 `true` 时启用；关闭时点合法终点直接走子
  （保持原有手感），启用后 MainWindow 从启动参数读取该开关；
- 启用后交互与五子棋对齐：第一次点合法终点只画**虚拟棋子**（`PENDING_TAG`），
  再点同一虚拟棋子才调用 `play_user_move`；点其它合法终点移动虚拟棋子；
- 虚拟棋子视觉：底色同真实棋子 + 棋子色虚线外环 + 内圈 + 汉字；
  终点有敌子时另套 `theme.CAPTURE_RING` 红环，明确提示这步是吃子；
- `XiangqiCanvas` 缓存 `_pending`，`<Configure>` 重放后恢复；`sync_board`、
  `clear_selection` 与改选棋子都会清除虚拟棋子；
- Esc / 右键分两级取消：先移除虚拟棋子（保留选子），再按一次取消选子；
- 新增测试：画布虚拟棋子绘制/吃子红环/清除时机/重放恢复，主窗口
  「预选不落子 → 二次点击确认」「切换落点」「Esc 两级取消」流程，以及
  配置默认关闭/`true` 启用与关闭时「点落点直接走子」两条路径。

### 5.6 `db` 与 `settings`

- **schema 零改动**：`games.game_type` 已预留；`moves.position` 是 TEXT，
  五子棋存 `"r,c"`、象棋存 ICCS `"h2e2"`，按 `game_type` 解析；
- `MoveRepository.add_move` 签名改为收 `position: str`（由 service 层
  经 `GameSpec.position_text` 格式化），调用点仅 `game_service.py`；
- `settings.py` 新增 `XIANGQI_ENGINE_PATH: str = ""`（空 = 默认
  `assets/engines/pikafish.exe`），`.env.example` 增加注释说明；
- 象棋与五子棋共库不拆分（避免老数据割裂）；默认库已由
  `runtime/data/gomoku.db` 更名为 `runtime/data/game.db`。

## 六、里程碑

延续既有编号（M1–M9 为五子棋阶段，见归档方案）：

| 里程碑 | 内容 | 验收标准 |
|---|---|---|
| **M10 规则内核** ✅ | `core/xiangqi/` 四文件 + 单测 | 七兵种走法（含蹩马腿/象眼/对脸/过河兵）、将军/将死/困毙、FEN 与 ICCS 往返、中文记法全绿；`ruff`/`mypy`/`pytest` 通过 |
| **M11 引擎封装** ✅ | `ai/xiangqi/`（uci + engine + 难度映射）+ **fake UCI 引擎**夹具 | bestmove/analyze/超时/进程崩溃/文件缺失各路径有测试；命令串行（锁）可验证；真机 Pikafish 冒烟通过（2026-10-19） |
| **M12 服务参数化** ✅ | `GameSpec` 重构 `GameService`/`CommentaryService`/`MoveRepository` | 现有 116 项测试不改断言全绿；象棋对局可入库（position=ICCS）；2026-10-19 完成，全仓 215 测试绿 |
| **M13 提示词与解说** ✅ | `XIANGQI_PROMPT`、`TurnResult.engine_eval`、mate 分显示 | 有/无 Key 两种路径回归；解说失败降级不阻断；2026-10-19 完成，真机评估→提示词链路冒烟通过 |
| **M14 画布与交互** ✅ | `xiangqi_canvas`、棋种切换、执红文案、建议显示、终局展示 | 选子→合法点位→落子全流程可用；Esc/右键取消；建议高亮起终点。2026-10-19 完成，全仓 262 测试绿，真机 Pikafish + Tk 冒烟（切换 → 炮二平五 → 马8进7 → 建议标记 → 关窗进程退出）通过 |
| **M15 打包与文档** ✅ | `build.py` 收集 `assets/engines/`、README/使用说明/CHANGELOG、Pikafish 下载指引 | 2026-10-19 完成 v1.1.0：产物内含 Pikafish 时附 GPL-3.0 许可说明（缺失则放下载指引并禁用象棋）；打包 exe 实测：带引擎可切象棋并从 dist 路径拉起 Pikafish，去引擎后启动只记「Pikafish 引擎未找到」警告、五子棋照常 |
| **M16 体验优化** ✅ | 棋盘点位/覆盖层/悔棋/将军/评估 | 2026-10-19 完成，全仓 286 测试绿（详见 5.7） |
| **M17 虚拟棋子** ✅ | 象棋先预选、二次点击确认（配置开关，默认关闭） | 2026-10-20 完成：`XIANGQI_VIRTUAL_PIECE=false` 时点落点直接走子；开启后预选不改变棋局、可改选/取消，吃子红环、尺寸变化重放恢复；详见 5.8 |

## 七、测试策略

- **core**：逐兵种走法表驱动用例；经典杀局样本（如最短将死局）验证
  `winner`/`check_win`；`undo` 恢复被吃子；FEN 往返一致性；
- **ai**：不依赖真 Pikafish——`tests/fixtures/fake_uci_engine.py`
  （约 40 行脚本：stdin 读命令，固定回 `uciok/readyok/bestmove`，
  可注入延迟与崩溃）覆盖正常/超时/崩溃/缺失路径，CI 可跑；
- **services**：参数化后五子棋全量回归 + 象棋编排（含 ICCS 入库断言）；
- **ui**：沿用「Tk 不可用即跳过」模式；坐标换算等纯逻辑抽函数单测；
- 真机 Pikafish 冒烟（本地手动）：四档难度、长考、切换、退出清理进程。

## 八、风险与对策

| 风险 | 对策 |
|---|---|
| **GPL 许可**：Pikafish 及 NNUE 权重为 GPL-3.0，随包分发需附许可文本与源码获取方式 | 官方分发**不内置引擎 exe/权重**，用户按文档自行下载放入 `assets/engines/`；自用打包时 `build.py` 若检测到本地存在则拷贝，并在分发物中附 GPL-3.0 文本与源码链接 |
| CPU 指令集不匹配（AVX2 等导致启动即退出） | 下载指引说明按 CPU 选构建（sse41-popcnt / avx2 / bmi2）；引擎握手失败文案提示「可能是指令集版本不符」 |
| 引擎长考阻塞建议线程 | 单实例串行（锁）；建议 movetime 封顶 3 秒 |
| 路径含空格/中文导致子进程启动失败 | 参数列表传递（非 shell 拼接）；exe 目录设为 `cwd` |
| 引擎与本地规则判定不一致（极端局面） | 引擎走子仍过 `place()` 校验，异常走 `ai_error` 降级，不写脏状态 |
| 长将/长捉未实现 | 首版接受（现实对局少见）；Backlog 记录 |
| NNUE 权重未随 exe 就位 | 引擎目录约定同放 `pikafish.nnue`；探测不到时按引擎默认/提示处理 |

## 九、Backlog（可选增强，暂不实施）

- 内置纯 Python 简易引擎兜底（引擎缺失也能玩，棋力弱）
- MultiPV=3 喂给 LLM 丰富解说；同一 FEN 解说缓存省 token
- PGN/棋谱导出（含每步引擎评分）；自适应思考时间（按局面阶段分配）
- `UCI_Elo` 精确限棋力；长将/长捉禁着
- ~~悔棋功能~~（M16 已实现，两棋种通用）

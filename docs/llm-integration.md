# LLM 接入说明

## 四家模型（全部走 OpenAI 兼容接口）

| 名称 | base_url | 默认模型 | 环境变量前缀 |
|---|---|---|---|
| DeepSeek | `https://api.deepseek.com` | `deepseek-chat` | `DEEPSEEK_` |
| Kimi | `https://api.moonshot.cn/v1` | `moonshot-v1-8k` | `KIMI_` |
| GLM | `https://open.bigmodel.cn/api/paas/v4` | `glm-4-flash` | `GLM_` |
| 豆包 | `https://ark.cn-beijing.volces.com/api/v3` | endpoint-id | `DOUBAO_` |

在 `.env` 中填任意一家的 `*_API_KEY` 即可；多填多家则 UI 下拉可切换。
豆包的 `DOUBAO_MODEL` 填接入点 ID（`ep-xxxx`）。

API Key 是可选的：一个都不填也能启动，此时 UI 模型下拉只有「空白」，
不进行 LLM 解说；AI 对弈与本地的「建议落子」仍完全可用。

## 调用链路

```
AI 落子（本地引擎）
  → CommentaryService.generate（后台线程）
    → prompts.build_gomoku_prompt（棋盘文本化 + 完整对局记录 + 任务说明）
    → OpenAICompatClient.stream_commentary（stream=True）
    → 每个文本块经 queue 回主线程 → AnalysisPanel.append_chunk
    → 完成后 on_done 回填 moves.llm_commentary
```

## 降级策略

`llm/fallback.py` 捕获全部异常（网络/超时/鉴权/限流），统一返回
"解说不可用"文案并记 `WARNING` 日志，对局照常进行。
日志中不打印 API Key；DEBUG 级别仅记录模型名与 prompt 长度。

## 提示词模板

`llm/prompts.py` 按棋种分模板。五子棋模板包含：

1. 规则说明（15×15 黑先无禁手）；
2. 文本化棋盘（0 空 / 1 黑 / 2 白，带行列号）；
3. 双方刚走的位置（A1 风格坐标）；
4. 完整对局记录（按落子顺序，便于模型核对已占用坐标）；
5. 三段式任务：拆解用户意图 → 解释 AI 理由 → 预判 2~3 步；
6. 输出约束：简洁分段、≤150 字、无棋盘图、不给落子建议。

落子建议不经过 LLM：由本地引擎在 AI 落子后按“当前难度 +1 层”搜索给出
（`GameService.suggest_for_user`，封顶 5 层；专家难度保持同深度），
因此不存在模型给出已占用坐标的问题，跟随建议也有实际胜算。

新增棋种时在 `prompts.py` 加对应模板即可，服务层不需要改。

## 用量提示

每步调用一次，一局约 20~40 次请求。`max_tokens=800`、流式输出以降低等待感。
如需控制成本可在 UI 切换到廉价模型（如 `glm-4-flash`）。

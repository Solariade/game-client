# 开发脚本

以下脚本用于本地调试与冒烟验证，不参与打包。

| 脚本 | 用途 | 是否会调用真实 API |
|---|---|---|
| `bench_engine.py` | 测试各难度搜索耗时与节点数 | 否 |
| `smoke_llm.py` | 用 `.env` 默认模型验证流式解说 | **是，会产生费用** |
| `smoke_e2e.py` | 模拟落子、AI 回应、解说回填与落库全链路 | 是（需已配置模型） |
| `smoke_order.py` | 用慢速假模型验证解说顺序、作废与建议落子 | 否（使用假客户端） |

```powershell
uv run python scripts/bench_engine.py
uv run python scripts/smoke_llm.py
uv run python scripts/smoke_e2e.py
uv run python scripts/smoke_order.py
```

冒烟脚本会创建隐藏的 Tk 窗口并自动退出，退出码 `0` 表示全部断言通过。

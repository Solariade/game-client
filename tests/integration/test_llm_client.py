"""LLM 客户端集成测试：respx 拦截 HTTP，不打真实 API。

同时覆盖 commentary_service 流式聚合与 fallback 降级。
"""

from __future__ import annotations

import pytest
import respx
from httpx import Response

from app.core.base_game import Move
from app.core.gomoku.board import GomokuBoard
from app.llm.fallback import FALLBACK_TEXT
from app.llm.openai_compat import OpenAICompatClient
from app.services.commentary_service import CommentaryService

BASE_URL = "https://api.test-llm.example/v1"


def make_client() -> OpenAICompatClient:
    return OpenAICompatClient(
        name="test",
        display_name="Test",
        api_key="sk-test",
        base_url=BASE_URL,
        model="test-chat",
    )


def sse_lines(*pieces: str) -> str:
    """构造 OpenAI 兼容流式 SSE 响应体。"""
    events = []
    for p in pieces:
        chunk = {
            "id": "c1",
            "object": "chat.completion.chunk",
            "choices": [{"index": 0, "delta": {"content": p}, "finish_reason": None}],
        }
        events.append(f"data: {chunk_json(chunk)}")
    events.append(
        'data: {"id":"c1","object":"chat.completion.chunk","choices":[{"index":0,"delta":{},"finish_reason":"stop"}]}'
    )
    events.append("data: [DONE]")
    return "\n\n".join(events) + "\n\n"


def chunk_json(obj: dict) -> str:
    import json

    return json.dumps(obj, ensure_ascii=False)


class TestOpenAICompatClient:
    @respx.mock
    def test_stream_yields_chunks(self) -> None:
        route = respx.post(f"{BASE_URL}/chat/completions").mock(
            return_value=Response(200, text=sse_lines("你这一步", "意在连三。"))
        )
        client = make_client()
        got = list(client.stream_commentary("prompt"))
        assert got == ["你这一步", "意在连三。"]
        assert route.called

    @respx.mock
    def test_request_carries_model(self) -> None:
        route = respx.post(f"{BASE_URL}/chat/completions").mock(
            return_value=Response(200, text=sse_lines("ok"))
        )
        client = make_client()
        list(client.stream_commentary("prompt"))
        body = route.calls.last.request.content.decode("utf-8")
        assert '"model":"test-chat"' in body
        assert "sk-test" not in body  # Key 不出现在请求体日志

    @respx.mock
    def test_auth_error_raises(self) -> None:
        respx.post(f"{BASE_URL}/chat/completions").mock(
            return_value=Response(401, json={"error": {"message": "bad key"}})
        )
        client = make_client()
        from openai import AuthenticationError

        with pytest.raises(AuthenticationError):
            list(client.stream_commentary("prompt"))


class TestCommentaryService:
    @respx.mock
    def test_generate_aggregates_and_calls_backs(self) -> None:
        respx.post(f"{BASE_URL}/chat/completions").mock(
            return_value=Response(
                200, text=sse_lines("拆招：", "你走H8想成三。", "预判：", "我挡I9。")
            )
        )
        board = GomokuBoard()
        board.place(Move(7, 7), 1)
        board.place(Move(7, 8), -1)
        chunks: list[str] = []
        done: list[str] = []
        full = CommentaryService().generate(
            make_client(),
            "提示词（棋种无关）",
            on_chunk=chunks.append,
            on_done=done.append,
        )
        assert full == "拆招：你走H8想成三。预判：我挡I9。"
        assert len(chunks) == 4
        assert done == [full]

    @respx.mock
    def test_generate_falls_back_on_error(self) -> None:
        respx.post(f"{BASE_URL}/chat/completions").mock(return_value=Response(500))
        board = GomokuBoard()
        board.place(Move(7, 7), 1)
        board.place(Move(7, 8), -1)
        full = CommentaryService().generate(make_client(), "提示词（棋种无关）")
        assert full == FALLBACK_TEXT

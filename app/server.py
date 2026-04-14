from __future__ import annotations

import json
import uuid
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Callable, Generator

from fastapi import FastAPI, HTTPException
from fastapi.responses import FileResponse, StreamingResponse
from pydantic import BaseModel, Field

from app.config import ModelConfig, Settings, load_conversation_config, load_settings
from app.conversation_store import ConversationStore
from app.llm import run_turn, run_turn_stream
from app.tools import ToolRegistry


class ChatRequest(BaseModel):
    conversation_id: str | None = None
    model: str = Field(..., min_length=1)
    message: str = Field(..., min_length=1)
    stream: bool = False


@dataclass
class AppState:
    settings: Settings
    conversations: ConversationStore
    registry: ToolRegistry
    run_turn_impl: Callable[..., dict[str, Any]]
    run_turn_stream_impl: Callable[..., Generator[dict[str, Any], None, None]]


def _coerce_settings(fake_settings: dict[str, Any]) -> Settings:
    models = [
        ModelConfig(
            id=item["id"],
            label=item["label"],
            api_key=item.get("api_key", "test-key"),
            base_url=item.get("base_url", "https://example.invalid/v1"),
            model_name=item["model_name"],
            protocol=item.get("protocol", "openai"),
        )
        for item in fake_settings["models"]
    ]
    return Settings(models=models)


def create_app(
    fake_settings: dict[str, Any] | None = None,
    run_turn_impl: Callable[..., dict[str, Any]] = run_turn,
    run_turn_stream_impl: Callable[
        ..., Generator[dict[str, Any], None, None]
    ] = run_turn_stream,
) -> FastAPI:
    settings = (
        _coerce_settings(fake_settings)
        if fake_settings is not None
        else load_settings()
    )
    conv_config = load_conversation_config() if fake_settings is None else {}
    app = FastAPI(title="A股智能分析助手")
    state = AppState(
        settings=settings,
        conversations=ConversationStore(
            max_messages=conv_config.get("max_messages", 50),
            ttl_seconds=conv_config.get("ttl_seconds", 3600),
            max_conversations=conv_config.get("max_conversations", 1000),
        ),
        registry=ToolRegistry(),
        run_turn_impl=run_turn_impl,
        run_turn_stream_impl=run_turn_stream_impl,
    )
    app.state.app_state = state

    @app.get("/")
    def index() -> FileResponse:
        static_path = Path(__file__).resolve().parent.parent / "static" / "index.html"
        if not static_path.exists():
            raise HTTPException(status_code=404, detail="UI not built yet")
        return FileResponse(static_path)

    @app.get("/models")
    def models() -> list[dict[str, str]]:
        return [
            {"id": model.id, "label": model.label, "model_name": model.model_name}
            for model in state.settings.models
        ]

    @app.post("/chat")
    def chat(request: ChatRequest) -> Any:
        conversation_id = request.conversation_id or str(uuid.uuid4())
        history = list(state.conversations.get(conversation_id))

        if request.stream:
            return StreamingResponse(
                _sse_generator(state, conversation_id, history, request),
                media_type="text/event-stream",
                headers={
                    "Cache-Control": "no-cache",
                    "X-Accel-Buffering": "no",
                },
            )

        result = state.run_turn_impl(
            settings=state.settings,
            model_id=request.model,
            history=history,
            user_message=request.message,
            registry=state.registry,
        )
        state.conversations.put(conversation_id, result["messages"])
        return {
            "conversation_id": conversation_id,
            "assistant": result["assistant_text"],
            "events": result["events"],
        }

    def _sse_generator(
        state: AppState,
        conversation_id: str,
        history: list[dict[str, Any]],
        request: ChatRequest,
    ) -> Generator[str, None, None]:
        final_messages = None
        final_text = ""
        try:
            for event in state.run_turn_stream_impl(
                settings=state.settings,
                model_id=request.model,
                history=history,
                user_message=request.message,
                registry=state.registry,
            ):
                if event["type"] == "token":
                    yield f"data: {json.dumps({'type': 'token', 'content': event['content']}, ensure_ascii=False)}\n\n"
                elif event["type"] == "tool_call":
                    yield f"data: {json.dumps({'type': 'tool_call', 'name': event['name']}, ensure_ascii=False)}\n\n"
                elif event["type"] == "tool_result":
                    yield f"data: {json.dumps({'type': 'tool_result', 'name': event['name']}, ensure_ascii=False)}\n\n"
                elif event["type"] == "done":
                    final_messages = event["messages"]
                    final_text = event["assistant_text"]
        except Exception as exc:
            yield f"data: {json.dumps({'type': 'error', 'message': str(exc)}, ensure_ascii=False)}\n\n"
            return

        if final_messages is not None:
            state.conversations.put(conversation_id, final_messages)
        yield f"data: {json.dumps({'type': 'done', 'conversation_id': conversation_id, 'assistant': final_text}, ensure_ascii=False)}\n\n"

    return app

from fastapi.testclient import TestClient

from app.server import create_app


def test_models_endpoint_returns_enabled_models():
    app = create_app(
        fake_settings={
            "models": [
                {"id": "glm", "label": "GLM", "model_name": "glm-5.1"},
                {
                    "id": "openai",
                    "label": "OpenAI Compatible",
                    "model_name": "deepseek-v3",
                },
            ]
        }
    )
    client = TestClient(app)

    response = client.get("/models")

    assert response.status_code == 200
    assert response.json()[0]["id"] == "glm"


def test_index_page_returns_chat_ui():
    app = create_app(
        fake_settings={
            "models": [{"id": "glm", "label": "GLM", "model_name": "glm-5.1"}]
        }
    )
    client = TestClient(app)

    response = client.get("/")

    assert response.status_code == 200
    assert "A股智能分析助手" in response.text
    assert "conversation-list" in response.text


def test_chat_endpoint_returns_assistant_message_and_events():
    def fake_runner(settings, model_id, history, user_message, registry):
        assert model_id == "glm"
        assert user_message == "帮我分析贵州茅台"
        return {
            "assistant_text": "测试回复",
            "events": [{"type": "tool_call", "name": "get_stock_price"}],
            "messages": history
            + [
                {"role": "user", "content": user_message},
                {"role": "assistant", "content": "测试回复"},
            ],
        }

    app = create_app(
        fake_settings={
            "models": [{"id": "glm", "label": "GLM", "model_name": "glm-5.1"}]
        },
        run_turn_impl=fake_runner,
    )
    client = TestClient(app)

    response = client.post(
        "/chat",
        json={
            "conversation_id": "conv-1",
            "model": "glm",
            "message": "帮我分析贵州茅台",
        },
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["conversation_id"] == "conv-1"
    assert payload["assistant"] == "测试回复"
    assert payload["events"] == [{"type": "tool_call", "name": "get_stock_price"}]


def test_streaming_chat_endpoint_emits_sse_events():
    def fake_stream_runner(settings, model_id, history, user_message, registry):
        yield {"type": "token", "content": "pong"}
        yield {
            "type": "done",
            "assistant_text": "pong",
            "messages": history
            + [
                {"role": "user", "content": user_message},
                {"role": "assistant", "content": "pong"},
            ],
        }

    app = create_app(
        fake_settings={
            "models": [
                {"id": "openai", "label": "OpenAI Compatible", "model_name": "gpt-5.4"}
            ]
        },
        run_turn_stream_impl=fake_stream_runner,
    )
    client = TestClient(app)

    with client.stream(
        "POST",
        "/chat",
        json={
            "conversation_id": "conv-stream",
            "model": "openai",
            "message": "Reply with exactly: pong",
            "stream": True,
        },
    ) as response:
        body = "".join(response.iter_text())

    assert response.status_code == 200
    assert '"type": "token"' in body
    assert '"content": "pong"' in body
    assert '"type": "done"' in body


def test_conversation_history_is_truncated_in_memory():
    def fake_runner(settings, model_id, history, user_message, registry):
        return {
            "assistant_text": "ok",
            "events": [],
            "messages": history
            + [
                {"role": "user", "content": user_message},
                {"role": "assistant", "content": "ok"},
            ],
        }

    app = create_app(
        fake_settings={
            "models": [{"id": "glm", "label": "GLM", "model_name": "glm-5.1"}]
        },
        run_turn_impl=fake_runner,
    )
    client = TestClient(app)

    for i in range(30):
        client.post(
            "/chat",
            json={"conversation_id": "conv-1", "model": "glm", "message": f"msg-{i}"},
        )

    state = app.state.app_state
    history = state.conversations.get("conv-1")
    assert len(history) <= 50

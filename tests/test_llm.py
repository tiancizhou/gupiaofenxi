from app.config import ModelConfig, Settings
from app.llm import run_turn, run_turn_stream
from app.tools import ToolRegistry


class _FakeFunc:
    def __init__(self, name, arguments):
        self.name = name
        self.arguments = arguments


class _FakeToolCall:
    def __init__(self, id, name, arguments):
        self.id = id
        self.function = _FakeFunc(name, arguments)


class _FakeMessage:
    def __init__(self, content=None, tool_calls=None):
        self.content = content
        self.tool_calls = tool_calls or []

    def model_dump(self):
        d = {"role": "assistant"}
        d["content"] = self.content
        if self.tool_calls:
            d["tool_calls"] = [
                {
                    "id": tc.id,
                    "type": "function",
                    "function": {
                        "name": tc.function.name,
                        "arguments": tc.function.arguments,
                    },
                }
                for tc in self.tool_calls
            ]
        return d


class _FakeChoice:
    def __init__(self, message):
        self.message = message


class _FakeResponse:
    def __init__(self, message):
        self.choices = [_FakeChoice(message)]


class FakeClient:
    def __init__(self, responses):
        self._responses = list(responses)
        self.requests = []

    @property
    def chat(self):
        return self

    @property
    def completions(self):
        return self

    def create(self, **kwargs):
        self.requests.append(kwargs)
        return self._responses.pop(0)


class FakeAnthropicResponse:
    def __init__(self, lines):
        self._lines = lines

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc, tb):
        return False

    def raise_for_status(self):
        return None

    def iter_lines(self):
        for line in self._lines:
            yield line


class FakeAnthropicClient:
    def __init__(self, responses):
        self._responses = list(responses)

    def stream(self, method, path, json):
        return self._responses.pop(0)


def test_run_turn_executes_tool_calls():
    settings = Settings(
        models=[
            ModelConfig(
                id="glm",
                label="GLM",
                api_key="test-key",
                base_url="https://glm.example/v1",
                model_name="glm-5.1",
                protocol="openai",
            )
        ]
    )
    registry = ToolRegistry({"ping": lambda **_: {"ok": True, "value": "pong"}})
    client = FakeClient(
        responses=[
            _FakeResponse(
                _FakeMessage(
                    tool_calls=[
                        _FakeToolCall("call_1", "ping", "{}"),
                    ]
                )
            ),
            _FakeResponse(_FakeMessage(content="final answer")),
        ]
    )

    result = run_turn(
        settings=settings,
        model_id="glm",
        history=[],
        user_message="say hi",
        registry=registry,
        client_factory=lambda _: client,
    )

    assert result["assistant_text"] == "final answer"
    assert result["events"][0] == {"type": "tool_call", "name": "ping"}
    assert result["events"][1]["type"] == "tool_result"
    assert result["events"][1]["result"] == {"ok": True, "value": "pong"}


def test_run_turn_stream_supports_anthropic_text_deltas(monkeypatch):
    settings = Settings(
        models=[
            ModelConfig(
                id="glm",
                label="GLM",
                api_key="test-key",
                base_url="https://glm.example/anthropic",
                model_name="glm-5.1",
                protocol="anthropic",
            )
        ]
    )
    registry = ToolRegistry({})
    fake_client = FakeAnthropicClient(
        [
            FakeAnthropicResponse(
                [
                    "event: content_block_delta",
                    'data: {"type":"content_block_delta","delta":{"type":"text_delta","text":"你"}}',
                    "",
                    "event: content_block_delta",
                    'data: {"type":"content_block_delta","delta":{"type":"text_delta","text":"好"}}',
                    "",
                    "event: message_stop",
                    'data: {"type":"message_stop"}',
                    "",
                ]
            )
        ]
    )

    monkeypatch.setattr("app.llm.create_anthropic_client", lambda model: fake_client)

    events = list(
        run_turn_stream(
            settings=settings,
            model_id="glm",
            history=[],
            user_message="hi",
            registry=registry,
        )
    )

    assert events[0] == {"type": "token", "content": "你"}
    assert events[1] == {"type": "token", "content": "好"}
    assert events[-1]["type"] == "done"
    assert events[-1]["assistant_text"] == "你好"

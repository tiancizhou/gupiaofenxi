# Stock Analysis Assistant Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Build a minimal, runnable single-user A-share chat assistant with a FastAPI backend, OpenAI-compatible LLM tool-calling, stock data tools, and a single-page web UI.

**Architecture:** Keep the first version as a small Python monolith. FastAPI serves one static page and a chat API; `llm.py` owns the model/provider selection and tool-call loop; `tools.py` wraps A-share data access and screener logic behind structured JSON-returning functions. Use in-memory conversation storage and browser localStorage to avoid adding a database.

**Tech Stack:** Python 3.11+, FastAPI, Uvicorn, OpenAI Python SDK, AkShare, python-dotenv, pytest, httpx.

---

### Task 1: Project scaffolding and dependencies

**Files:**
- Create: `requirements.txt`
- Create: `.gitignore`
- Create: `app/__init__.py`
- Create: `tests/__init__.py`

**Step 1: Write the failing test**

```python
def test_import_app_package():
    import app
    assert app is not None
```

**Step 2: Run test to verify it fails**

Run: `pytest tests/test_smoke.py::test_import_app_package -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'app'`

**Step 3: Write minimal implementation**

```python
# app/__init__.py
__all__ = []
```

Create a minimal `requirements.txt` with:

```text
fastapi
uvicorn
openai
python-dotenv
akshare
httpx
pytest
```

Create `.gitignore` with:

```text
__pycache__/
.pytest_cache/
.venv/
.env
```

**Step 4: Run test to verify it passes**

Run: `pytest tests/test_smoke.py::test_import_app_package -v`
Expected: PASS

**Step 5: Commit**

```bash
git add requirements.txt .gitignore app/__init__.py tests/__init__.py tests/test_smoke.py
git commit -m "chore: add python project scaffold"
```

### Task 2: Provider config and model registry

**Files:**
- Create: `app/config.py`
- Create: `tests/test_config.py`

**Step 1: Write the failing test**

```python
from app.config import load_settings


def test_load_settings_reads_enabled_models(monkeypatch):
    monkeypatch.setenv("LLM_GLM_API_KEY", "glm-key")
    monkeypatch.setenv("LLM_GLM_BASE_URL", "https://glm.example/v1")
    monkeypatch.setenv("LLM_GLM_MODEL", "glm-5.1")
    monkeypatch.setenv("LLM_OPENAI_API_KEY", "openai-key")
    monkeypatch.setenv("LLM_OPENAI_BASE_URL", "https://proxy.example/v1")
    monkeypatch.setenv("LLM_OPENAI_MODEL", "deepseek-v3")

    settings = load_settings()

    assert [model.id for model in settings.models] == ["glm", "openai"]
```
```

**Step 2: Run test to verify it fails**

Run: `pytest tests/test_config.py::test_load_settings_reads_enabled_models -v`
Expected: FAIL with `ModuleNotFoundError` or missing symbol error

**Step 3: Write minimal implementation**

Implement:
- `ModelConfig` dataclass with fields `id`, `label`, `api_key`, `base_url`, `model_name`
- `Settings` dataclass with `models: list[ModelConfig]`
- `load_settings()` that reads env vars, includes only fully configured models, and raises a clear `RuntimeError` if none are configured

**Step 4: Run test to verify it passes**

Run: `pytest tests/test_config.py -v`
Expected: PASS

**Step 5: Commit**

```bash
git add app/config.py tests/test_config.py
git commit -m "feat: add model provider configuration"
```

### Task 3: Stock tools interface and deterministic tests

**Files:**
- Create: `app/tools.py`
- Create: `tests/test_tools.py`

**Step 1: Write the failing test**

```python
from app.tools import infer_market, get_tool_definitions


def test_infer_market_from_a_share_code():
    assert infer_market("600519") == "sh"
    assert infer_market("000001") == "sz"


def test_get_tool_definitions_includes_screener():
    names = [tool["function"]["name"] for tool in get_tool_definitions()]
    assert "screen_stocks" in names
```
```

**Step 2: Run test to verify it fails**

Run: `pytest tests/test_tools.py -v`
Expected: FAIL because `app.tools` does not exist

**Step 3: Write minimal implementation**

Implement in `app/tools.py`:
- `infer_market(code: str) -> str`
- `get_tool_definitions() -> list[dict]`
- `ToolRegistry` that maps tool names to Python callables
- First-pass tool stubs:
  - `get_stock_price`
  - `get_stock_info`
  - `get_financial_indicators`
  - `get_stock_news`
  - `get_market_sentiment`
  - `get_global_news`
  - `screen_stocks`

Each tool should:
- accept plain JSON-like arguments
- return a JSON-serializable dict
- catch provider/data errors and return `{ "ok": False, "error": ... }`

Use helper functions so tests can monkeypatch AkShare calls directly.

**Step 4: Run test to verify it passes**

Run: `pytest tests/test_tools.py -v`
Expected: PASS

**Step 5: Commit**

```bash
git add app/tools.py tests/test_tools.py
git commit -m "feat: add stock tool registry"
```

### Task 4: LLM client and tool-call loop

**Files:**
- Create: `app/llm.py`
- Create: `tests/test_llm.py`

**Step 1: Write the failing test**

```python
from app.llm import run_turn


class FakeRegistry:
    def get_tool_definitions(self):
        return [{"type": "function", "function": {"name": "ping", "parameters": {"type": "object", "properties": {}}}}]

    def call(self, name, arguments):
        assert name == "ping"
        return {"ok": True, "value": "pong"}


def test_run_turn_executes_tool_calls():
    class FakeClient:
        def __init__(self):
            self.calls = 0

        def responses(self):
            raise AssertionError("SDK shape changed")
```

Add a simpler injectable API in the real code so tests can feed:
- first model response with one tool call
- second model response with final text

Assert final output contains the final assistant text and the tool result was consumed.
```

**Step 2: Run test to verify it fails**

Run: `pytest tests/test_llm.py -v`
Expected: FAIL because `run_turn` does not exist

**Step 3: Write minimal implementation**

Implement in `app/llm.py`:
- `build_system_prompt()`
- `create_client(model_config)`
- `run_turn(settings, model_id, history, user_message, registry, client_factory=...)`

Behavior:
- choose the configured model by `model_id`
- send `system + history + user_message`
- include tool definitions
- if model returns tool calls, execute them and continue
- stop when model returns final text
- return a dict like:

```python
{
    "assistant_text": "...",
    "events": [
        {"type": "tool_call", "name": "get_stock_price"},
        {"type": "tool_result", "name": "get_stock_price", "result": {...}}
    ]
}
```

Keep the implementation synchronous first. Add a separate adapter in `server.py` for streaming the final text in chunks.

**Step 4: Run test to verify it passes**

Run: `pytest tests/test_llm.py -v`
Expected: PASS

**Step 5: Commit**

```bash
git add app/llm.py tests/test_llm.py
git commit -m "feat: add llm tool calling loop"
```

### Task 5: FastAPI app and endpoints

**Files:**
- Create: `app/server.py`
- Create: `tests/test_server.py`

**Step 1: Write the failing test**

```python
from fastapi.testclient import TestClient
from app.server import create_app


def test_models_endpoint_returns_enabled_models(monkeypatch):
    app = create_app(fake_settings={
        "models": [
            {"id": "glm", "label": "GLM", "model_name": "glm-5.1"}
        ]
    })
    client = TestClient(app)

    response = client.get("/models")

    assert response.status_code == 200
    assert response.json()[0]["id"] == "glm"
```

Add another test for `POST /chat` that monkeypatches `run_turn` and verifies JSON response includes assistant text and events.
```

**Step 2: Run test to verify it fails**

Run: `pytest tests/test_server.py -v`
Expected: FAIL because server module/app factory is missing

**Step 3: Write minimal implementation**

Implement:
- `create_app()` factory
- `GET /models`
- `POST /chat`
- static file serving for `/`

Request shape:

```json
{
  "conversation_id": "optional-string",
  "model": "glm",
  "message": "帮我分析贵州茅台"
}
```

Response shape for MVP:

```json
{
  "conversation_id": "...",
  "assistant": "...",
  "events": [...]
}
```

Use a simple in-memory dict keyed by `conversation_id` to retain message history.

**Step 4: Run test to verify it passes**

Run: `pytest tests/test_server.py -v`
Expected: PASS

**Step 5: Commit**

```bash
git add app/server.py tests/test_server.py
git commit -m "feat: add fastapi chat service"
```

### Task 6: Single-page chat UI

**Files:**
- Create: `static/index.html`
- Create: `.env.example`

**Step 1: Write the failing test**

Use a simple response test in `tests/test_server.py` to verify `GET /` returns HTML containing:

```python
assert "A股智能分析助手" in response.text
assert "conversation-list" in response.text
```

**Step 2: Run test to verify it fails**

Run: `pytest tests/test_server.py::test_index_page -v`
Expected: FAIL because no static page exists yet

**Step 3: Write minimal implementation**

Implement `static/index.html` with:
- left sidebar for conversation list
- model select dropdown
- chat message area
- composer form
- plain fetch to `POST /chat`
- localStorage persistence for conversation metadata

Create `.env.example` with both provider groups documented.

**Step 4: Run test to verify it passes**

Run: `pytest tests/test_server.py -v`
Expected: PASS

**Step 5: Commit**

```bash
git add static/index.html .env.example tests/test_server.py
git commit -m "feat: add chat web interface"
```

### Task 7: End-to-end verification

**Files:**
- Modify: `README.md` (optional if created during implementation)

**Step 1: Write the failing test**

No new code test required. This task is verification-only.

**Step 2: Run verification commands**

Run:

```bash
pytest -v
```

Expected: all tests PASS

Run:

```bash
uvicorn app.server:create_app --factory --host 127.0.0.1 --port 8000
```

Expected:
- server starts without import/config crash
- `GET /models` returns configured models after setting env vars
- `GET /` loads the UI

**Step 3: Fix any issues surfaced by verification**

Keep fixes minimal and re-run verification.

**Step 4: Commit**

```bash
git add .
git commit -m "test: verify stock analysis assistant mvp"
```

# 对话存储内存优化 Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** 限制对话历史长度 + 空闲对话超时自动清理，防止内存无限增长，不引入外部依赖。

**Architecture:** 新增 `ConversationStore` 类封装对话存储逻辑，替代原有 `dict`。支持：单条对话最大消息数截断、空闲对话 TTL 自动淘汰、最大对话数限制（LRU）。通过环境变量配置参数，零外部依赖。

**Tech Stack:** Python 3.11 标准库（`time`, `collections.OrderedDict`）

---

### Task 1: 创建 ConversationStore 类

**Files:**
- Create: `app/conversation_store.py`
- Test: `tests/test_conversation_store.py`

**Step 1: Write the failing test**

```python
import time

from app.conversation_store import ConversationStore


def test_put_and_get_messages():
    store = ConversationStore(max_messages=10, ttl_seconds=60, max_conversations=100)
    store.put("conv-1", [{"role": "user", "content": "hello"}])
    assert store.get("conv-1") == [{"role": "user", "content": "hello"}]


def test_get_missing_returns_empty_list():
    store = ConversationStore()
    assert store.get("nonexistent") == []


def test_truncate_old_messages():
    store = ConversationStore(max_messages=4, ttl_seconds=60, max_conversations=100)
    messages = [{"role": "user", "content": f"msg-{i}"} for i in range(6)]
    store.put("conv-1", messages)
    result = store.get("conv-1")
    assert len(result) == 4
    assert result[0]["content"] == "msg-2"


def test_expire_idle_conversation():
    store = ConversationStore(max_messages=10, ttl_seconds=0, max_conversations=100)
    store.put("conv-1", [{"role": "user", "content": "hello"}])
    time.sleep(0.1)
    assert store.get("conv-1") == []


def test_max_conversations_evicts_oldest():
    store = ConversationStore(max_messages=10, ttl_seconds=60, max_conversations=2)
    store.put("conv-1", [{"role": "user", "content": "a"}])
    store.put("conv-2", [{"role": "user", "content": "b"}])
    store.put("conv-3", [{"role": "user", "content": "c"}])
    assert store.get("conv-1") == []
    assert store.get("conv-2") == [{"role": "user", "content": "b"}]
    assert store.get("conv-3") == [{"role": "user", "content": "c"}]


def test_get_touches_conversation_preventing_lru_eviction():
    store = ConversationStore(max_messages=10, ttl_seconds=60, max_conversations=2)
    store.put("conv-1", [{"role": "user", "content": "a"}])
    store.put("conv-2", [{"role": "user", "content": "b"}])
    store.get("conv-1")
    store.put("conv-3", [{"role": "user", "content": "c"}])
    assert store.get("conv-1") == [{"role": "user", "content": "a"}]
    assert store.get("conv-2") == []
```

**Step 2: Run test to verify it fails**

Run: `python -m pytest tests/test_conversation_store.py -v`
Expected: FAIL (module not found)

**Step 3: Write minimal implementation**

```python
from __future__ import annotations

import time
from collections import OrderedDict
from typing import Any


class ConversationStore:
    def __init__(
        self,
        max_messages: int = 50,
        ttl_seconds: int = 3600,
        max_conversations: int = 1000,
    ) -> None:
        self._max_messages = max_messages
        self._ttl_seconds = ttl_seconds
        self._max_conversations = max_conversations
        self._data: OrderedDict[str, tuple[list[dict[str, Any]], float]] = OrderedDict()

    def get(self, conversation_id: str) -> list[dict[str, Any]]:
        if conversation_id not in self._data:
            return []
        messages, last_access = self._data[conversation_id]
        if time.monotonic() - last_access > self._ttl_seconds:
            del self._data[conversation_id]
            return []
        self._data.move_to_end(conversation_id)
        return messages

    def put(self, conversation_id: str, messages: list[dict[str, Any]]) -> None:
        trimmed = messages[-self._max_messages :]
        self._data[conversation_id] = (trimmed, time.monotonic())
        self._data.move_to_end(conversation_id)
        while len(self._data) > self._max_conversations:
            self._data.popitem(last=False)
```

**Step 4: Run test to verify it passes**

Run: `python -m pytest tests/test_conversation_store.py -v`
Expected: PASS

**Step 5: Commit**

```bash
git add app/conversation_store.py tests/test_conversation_store.py
git commit -m "feat: add ConversationStore with message truncation, TTL eviction, and LRU limit"
```

---

### Task 2: 集成 ConversationStore 到 server.py

**Files:**
- Modify: `app/server.py:26-64` (AppState + create_app)
- Modify: `tests/test_server.py` (验证兼容性)

**Step 1: Write the failing test**

在 `tests/test_server.py` 末尾添加：

```python
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
    assert len(history) <= 20
```

**Step 2: Run test to verify it fails**

Run: `python -m pytest tests/test_server.py::test_conversation_history_is_truncated_in_memory -v`
Expected: FAIL (len > 20，因为当前 dict 无截断)

**Step 3: Modify `app/server.py`**

将 `AppState` 中 `conversations` 从 `dict` 改为 `ConversationStore`：

```python
from app.conversation_store import ConversationStore
```

`AppState` 改为：

```python
@dataclass
class AppState:
    settings: Settings
    conversations: ConversationStore
    registry: ToolRegistry
    run_turn_impl: Callable[..., dict[str, Any]]
    run_turn_stream_impl: Callable[..., Generator[dict[str, Any], None, None]]
```

`create_app` 中初始化改为：

```python
state = AppState(
    settings=settings,
    conversations=ConversationStore(
        max_messages=20,
        ttl_seconds=3600,
        max_conversations=500,
    ),
    registry=ToolRegistry(),
    run_turn_impl=run_turn_impl,
    run_turn_stream_impl=run_turn_stream_impl,
)
```

所有 `state.conversations.get(conversation_id, [])` 改为 `state.conversations.get(conversation_id)`（`ConversationStore.get` 已默认返回 `[]`）。

所有 `state.conversations[conversation_id] = result["messages"]` 改为 `state.conversations.put(conversation_id, result["messages"])`。

**Step 4: Run all tests**

Run: `python -m pytest tests/ -v`
Expected: ALL PASS

**Step 5: Commit**

```bash
git add app/server.py tests/test_server.py
git commit -m "feat: integrate ConversationStore into server with memory limits"
```

---

### Task 3: 通过环境变量配置参数

**Files:**
- Modify: `app/config.py` (添加 `ConversationConfig`)
- Modify: `app/server.py` (从配置读取参数)
- Modify: `.env.example` (添加配置示例)
- Test: `tests/test_config.py`

**Step 1: Write the failing test**

在 `tests/test_config.py` 中添加：

```python
import os


def test_conversation_config_reads_from_env(monkeypatch):
    monkeypatch.setenv("CONV_MAX_MESSAGES", "30")
    monkeypatch.setenv("CONV_TTL_SECONDS", "7200")
    monkeypatch.setenv("CONV_MAX_CONVERSATIONS", "200")

    from app.config import load_conversation_config

    config = load_conversation_config(load_env=False)
    assert config["max_messages"] == 30
    assert config["ttl_seconds"] == 7200
    assert config["max_conversations"] == 200
```

**Step 2: Run test to verify it fails**

Run: `python -m pytest tests/test_config.py::test_conversation_config_reads_from_env -v`
Expected: FAIL (import error)

**Step 3: Add `load_conversation_config` to `app/config.py`**

```python
def load_conversation_config(load_env: bool = True) -> dict[str, int]:
    if load_env:
        load_dotenv()
    return {
        "max_messages": int(os.getenv("CONV_MAX_MESSAGES", "50")),
        "ttl_seconds": int(os.getenv("CONV_TTL_SECONDS", "3600")),
        "max_conversations": int(os.getenv("CONV_MAX_CONVERSATIONS", "1000")),
    }
```

**Step 4: Modify `app/server.py` 的 `create_app`，从配置读取参数**

```python
from app.config import ModelConfig, Settings, load_conversation_config, load_settings
```

`create_app` 中：

```python
conv_config = load_conversation_config() if fake_settings is None else {}
state = AppState(
    settings=settings,
    conversations=ConversationStore(
        max_messages=conv_config.get("max_messages", 50),
        ttl_seconds=conv_config.get("ttl_seconds", 3600),
        max_conversations=conv_config.get("max_conversations", 1000),
    ),
    ...
)
```

**Step 5: Update `.env.example`，添加**

```
# Conversation storage limits
CONV_MAX_MESSAGES=50
CONV_TTL_SECONDS=3600
CONV_MAX_CONVERSATIONS=1000
```

**Step 6: Run all tests**

Run: `python -m pytest tests/ -v`
Expected: ALL PASS

**Step 7: Commit**

```bash
git add app/config.py app/server.py .env.example tests/test_config.py
git commit -m "feat: make conversation storage limits configurable via env vars"
```

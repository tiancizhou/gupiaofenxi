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

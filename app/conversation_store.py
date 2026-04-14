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

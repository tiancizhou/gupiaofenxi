from __future__ import annotations

import json
from typing import Any, Callable, Generator

import httpx
from openai import OpenAI

from app.config import ModelConfig, Settings


def build_system_prompt() -> str:
    return (
        "你是一个A股智能分析助手。优先使用工具获取股票、财务、新闻和市场情绪数据，"
        "然后用中文输出结构化分析。不要编造数据，不确定时明确说明。\n\n"
        "A股代码规则：6开头为上海(sh)，0/3开头为深圳(sz)。\n\n"
        "可用工具说明：\n"
        "- get_stock_price: 查个股日K线行情\n"
        "- get_stock_info: 查个股基本信息\n"
        "- get_financial_indicators: 查财务指标摘要\n"
        "- get_stock_news: 查个股新闻\n"
        "- get_market_sentiment: 查涨停池、板块资金流等市场情绪\n"
        "- get_global_news: 查宏观/全球财经新闻\n"
        "- screen_stocks: 条件选股（跌幅回调+盈利筛选）\n"
    )


def create_client(model_config: ModelConfig) -> OpenAI:
    return OpenAI(api_key=model_config.api_key, base_url=model_config.base_url)


def create_anthropic_client(model_config: ModelConfig) -> httpx.Client:
    return httpx.Client(
        base_url=model_config.base_url,
        headers={
            "x-api-key": model_config.api_key,
            "anthropic-version": "2023-06-01",
            "content-type": "application/json",
        },
        timeout=60,
    )


def _build_messages(
    history: list[dict[str, Any]], user_message: str
) -> list[dict[str, Any]]:
    messages = [{"role": "system", "content": build_system_prompt()}]
    messages.extend(history)
    messages.append({"role": "user", "content": user_message})
    return messages


def _extract_tool_calls_from_chunk(
    chunk: Any, tool_call_buffers: dict[int, dict[str, Any]]
) -> list[dict[str, Any]]:
    delta = chunk.choices[0].delta
    if not hasattr(delta, "tool_calls") or delta.tool_calls is None:
        return []
    results = []
    for tc_delta in delta.tool_calls:
        idx = tc_delta.index
        if idx not in tool_call_buffers:
            tool_call_buffers[idx] = {"id": "", "name": "", "arguments": ""}
        buf = tool_call_buffers[idx]
        if tc_delta.id:
            buf["id"] = tc_delta.id
        if tc_delta.function:
            if tc_delta.function.name:
                buf["name"] = tc_delta.function.name
            if tc_delta.function.arguments:
                buf["arguments"] += tc_delta.function.arguments
        if chunk.choices[0].finish_reason == "tool_calls":
            results.append(
                {
                    "id": buf["id"],
                    "name": buf["name"],
                    "arguments": buf["arguments"],
                }
            )
    return results


def _parse_arguments(raw: str | dict) -> dict[str, Any]:
    if isinstance(raw, dict):
        return raw
    if isinstance(raw, str) and raw.strip():
        try:
            return json.loads(raw)
        except (json.JSONDecodeError, TypeError):
            return {}
    return {}


def _openai_tools_to_anthropic_tools(
    tools: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    anthropic_tools = []
    for tool in tools:
        function = tool["function"]
        anthropic_tools.append(
            {
                "name": function["name"],
                "description": function["description"],
                "input_schema": function["parameters"],
            }
        )
    return anthropic_tools


def _history_to_anthropic_messages(
    history: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    messages = []
    for item in history:
        role = item.get("role")
        if role in {"user", "assistant"}:
            messages.append({"role": role, "content": item.get("content", "")})
    return messages


def _run_turn_openai(
    model: ModelConfig,
    history: list[dict[str, Any]],
    user_message: str,
    registry: Any,
    client_factory: Callable[[ModelConfig], Any],
) -> dict[str, Any]:
    client = client_factory(model)
    messages = _build_messages(history, user_message)
    events: list[dict[str, Any]] = []

    while True:
        payload: dict[str, Any] = {
            "model": model.model_name,
            "messages": messages,
            "tools": registry.get_tool_definitions(),
        }
        response = client.chat.completions.create(**payload)
        message = response.choices[0].message

        tool_calls = getattr(message, "tool_calls", None) or []
        if not tool_calls:
            assistant_text = message.content or ""
            messages.append({"role": "assistant", "content": assistant_text})
            return {
                "assistant_text": assistant_text,
                "events": events,
                "messages": messages,
            }

        messages.append(message.model_dump())
        for call in tool_calls:
            name = call.function.name
            arguments = _parse_arguments(call.function.arguments)
            events.append({"type": "tool_call", "name": name})
            result = registry.call(name, arguments)
            events.append({"type": "tool_result", "name": name, "result": result})
            messages.append(
                {
                    "role": "tool",
                    "tool_call_id": call.id,
                    "name": name,
                    "content": json.dumps(result, ensure_ascii=False, default=str),
                }
            )


def _run_turn_anthropic(
    model: ModelConfig,
    history: list[dict[str, Any]],
    user_message: str,
    registry: Any,
) -> dict[str, Any]:
    client = create_anthropic_client(model)
    messages = _history_to_anthropic_messages(history)
    messages.append({"role": "user", "content": user_message})
    events: list[dict[str, Any]] = []
    tools = _openai_tools_to_anthropic_tools(registry.get_tool_definitions())

    while True:
        response = client.post(
            "/v1/messages",
            json={
                "model": model.model_name,
                "system": build_system_prompt(),
                "max_tokens": 4096,
                "messages": messages,
                "tools": tools,
            },
        )
        response.raise_for_status()
        payload = response.json()
        content = payload.get("content", [])

        tool_uses = [block for block in content if block.get("type") == "tool_use"]
        text_blocks = [
            block.get("text", "") for block in content if block.get("type") == "text"
        ]

        if not tool_uses:
            assistant_text = "".join(text_blocks)
            return {
                "assistant_text": assistant_text,
                "events": events,
                "messages": history
                + [
                    {"role": "user", "content": user_message},
                    {"role": "assistant", "content": assistant_text},
                ],
            }

        assistant_content = []
        tool_result_blocks = []
        for block in content:
            if block.get("type") == "tool_use":
                name = block["name"]
                arguments = block.get("input", {})
                events.append({"type": "tool_call", "name": name})
                result = registry.call(name, arguments)
                events.append({"type": "tool_result", "name": name, "result": result})
                assistant_content.append(block)
                tool_result_blocks.append(
                    {
                        "type": "tool_result",
                        "tool_use_id": block["id"],
                        "content": json.dumps(result, ensure_ascii=False, default=str),
                    }
                )
            elif block.get("type") == "text":
                assistant_content.append(block)

        messages.append({"role": "assistant", "content": assistant_content})
        messages.append({"role": "user", "content": tool_result_blocks})


def _stream_anthropic_events(response: Any) -> list[dict[str, Any]]:
    events: list[dict[str, Any]] = []
    current_event = None
    for raw_line in response.iter_lines():
        line = raw_line.decode() if isinstance(raw_line, bytes) else raw_line
        if line.startswith("event: "):
            current_event = line[7:]
            continue
        if not line.startswith("data: "):
            continue
        payload = json.loads(line[6:])
        payload["_event"] = current_event
        events.append(payload)
    return events


def _run_turn_stream_anthropic(
    model: ModelConfig,
    history: list[dict[str, Any]],
    user_message: str,
    registry: Any,
) -> Generator[dict[str, Any], None, None]:
    client = create_anthropic_client(model)
    messages = _history_to_anthropic_messages(history)
    messages.append({"role": "user", "content": user_message})
    tools = _openai_tools_to_anthropic_tools(registry.get_tool_definitions())

    while True:
        with client.stream(
            "POST",
            "/v1/messages",
            json={
                "model": model.model_name,
                "system": build_system_prompt(),
                "max_tokens": 4096,
                "messages": messages,
                "tools": tools,
                "stream": True,
            },
        ) as response:
            response.raise_for_status()
            raw_events = _stream_anthropic_events(response)

        assistant_text = ""
        tool_calls: list[dict[str, Any]] = []
        content_blocks: dict[int, dict[str, Any]] = {}

        for event in raw_events:
            if event.get("type") == "content_block_start":
                index = event.get("index", 0)
                block = event.get("content_block", {})
                content_blocks[index] = block
                if block.get("type") == "tool_use":
                    content_blocks[index]["input"] = ""
            elif event.get("type") == "content_block_delta":
                index = event.get("index", 0)
                delta = event.get("delta", {})
                if delta.get("type") == "text_delta":
                    text = delta.get("text", "")
                    assistant_text += text
                    yield {"type": "token", "content": text}
                elif delta.get("type") == "input_json_delta":
                    partial = delta.get("partial_json", "")
                    block = content_blocks.setdefault(
                        index, {"type": "tool_use", "input": ""}
                    )
                    block["input"] = block.get("input", "") + partial
            elif event.get("type") == "content_block_stop":
                index = event.get("index", 0)
                block = content_blocks.get(index, {})
                if block.get("type") == "tool_use":
                    tool_calls.append(
                        {
                            "id": block.get("id", f"tool_{index}"),
                            "name": block.get("name", ""),
                            "arguments": _parse_arguments(block.get("input", "")),
                        }
                    )

        if not tool_calls:
            yield {
                "type": "done",
                "assistant_text": assistant_text,
                "messages": history
                + [
                    {"role": "user", "content": user_message},
                    {"role": "assistant", "content": assistant_text},
                ],
            }
            return

        assistant_content = []
        tool_result_blocks = []
        if assistant_text:
            assistant_content.append({"type": "text", "text": assistant_text})

        for call in tool_calls:
            yield {"type": "tool_call", "name": call["name"]}
            result = registry.call(call["name"], call["arguments"])
            yield {"type": "tool_result", "name": call["name"], "result": result}
            assistant_content.append(
                {
                    "type": "tool_use",
                    "id": call["id"],
                    "name": call["name"],
                    "input": call["arguments"],
                }
            )
            tool_result_blocks.append(
                {
                    "type": "tool_result",
                    "tool_use_id": call["id"],
                    "content": json.dumps(result, ensure_ascii=False, default=str),
                }
            )

        messages.append({"role": "assistant", "content": assistant_content})
        messages.append({"role": "user", "content": tool_result_blocks})


def run_turn(
    settings: Settings,
    model_id: str,
    history: list[dict[str, Any]],
    user_message: str,
    registry: Any,
    client_factory: Callable[[ModelConfig], Any] = create_client,
) -> dict[str, Any]:
    model = settings.get_model(model_id)
    if model.protocol == "anthropic":
        return _run_turn_anthropic(model, history, user_message, registry)
    return _run_turn_openai(model, history, user_message, registry, client_factory)


def run_turn_stream(
    settings: Settings,
    model_id: str,
    history: list[dict[str, Any]],
    user_message: str,
    registry: Any,
    client_factory: Callable[[ModelConfig], Any] = create_client,
) -> Generator[dict[str, Any], None, None]:
    model = settings.get_model(model_id)
    if model.protocol == "anthropic":
        yield from _run_turn_stream_anthropic(model, history, user_message, registry)
        return

    client = client_factory(model)
    messages = _build_messages(history, user_message)

    while True:
        payload: dict[str, Any] = {
            "model": model.model_name,
            "messages": messages,
            "tools": registry.get_tool_definitions(),
            "stream": True,
        }
        stream = client.chat.completions.create(**payload)

        tool_call_buffers: dict[int, dict[str, Any]] = {}
        assistant_text = ""
        tool_calls_complete: list[dict[str, Any]] = []

        for chunk in stream:
            if not chunk.choices:
                continue
            delta = chunk.choices[0].delta
            finish_reason = chunk.choices[0].finish_reason

            if hasattr(delta, "content") and delta.content:
                assistant_text += delta.content
                yield {"type": "token", "content": delta.content}

            completed = _extract_tool_calls_from_chunk(chunk, tool_call_buffers)
            tool_calls_complete.extend(completed)

            if finish_reason in {"tool_calls", "stop"}:
                break

        if not tool_calls_complete:
            messages.append({"role": "assistant", "content": assistant_text})
            yield {
                "type": "done",
                "assistant_text": assistant_text,
                "messages": messages,
            }
            return

        assistant_msg = {"role": "assistant", "content": None, "tool_calls": []}
        for tc in tool_calls_complete:
            name = tc["name"]
            arguments = _parse_arguments(tc["arguments"])
            yield {"type": "tool_call", "name": name}
            result = registry.call(name, arguments)
            yield {"type": "tool_result", "name": name, "result": result}
            assistant_msg["tool_calls"].append(
                {
                    "id": tc["id"],
                    "type": "function",
                    "function": {"name": name, "arguments": arguments},
                }
            )
            messages.append(
                {
                    "role": "tool",
                    "tool_call_id": tc["id"],
                    "name": name,
                    "content": json.dumps(result, ensure_ascii=False, default=str),
                }
            )
        messages.append(assistant_msg)

"""LLM tool/function calling — provider-native format build + response parsing.

Handles Claude tool_use and OpenAI tool_calls wire formats.
"""

from __future__ import annotations

import json
from typing import Any, Dict, List


# --- Provider-native tool format builders ---

def build_tools_param_claude(tools: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """Convert tool registry entries to Claude's tool format.

    Claude format: {name, description, input_schema}
    """
    result = []
    for tool in tools:
        result.append({
            "name": tool["name"],
            "description": tool.get("description", ""),
            "input_schema": tool.get("parameters", {"type": "object", "properties": {}}),
        })
    return result


def build_tools_param_openai(tools: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """Convert tool registry entries to OpenAI's function calling format.

    OpenAI format: {type: "function", function: {name, description, parameters}}
    """
    result = []
    for tool in tools:
        result.append({
            "type": "function",
            "function": {
                "name": tool["name"],
                "description": tool.get("description", ""),
                "parameters": tool.get("parameters", {"type": "object", "properties": {}}),
            },
        })
    return result


def build_tools_param(provider_id: str, tools: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """Build provider-native tools parameter from tool registry entries."""
    if provider_id == "claude":
        return build_tools_param_claude(tools)
    # OpenAI-compatible format for openai, xai, deepseek, google, qwen
    return build_tools_param_openai(tools)


# --- Tool call extraction from responses ---

def extract_tool_calls_claude(resp_bytes: bytes) -> List[Dict[str, Any]]:
    """Extract tool_use blocks from Claude Messages API response.

    Returns: [{id, name, input}]
    """
    try:
        obj = json.loads(resp_bytes.decode("utf-8", errors="ignore"))
    except Exception:
        return []

    if not isinstance(obj, dict):
        return []

    content = obj.get("content")
    if not isinstance(content, list):
        return []

    calls = []
    for block in content:
        if not isinstance(block, dict):
            continue
        if block.get("type") == "tool_use":
            calls.append({
                "id": block.get("id", ""),
                "name": block.get("name", ""),
                "input": block.get("input", {}),
            })
    return calls


def extract_tool_calls_openai(resp_bytes: bytes) -> List[Dict[str, Any]]:
    """Extract tool_calls from OpenAI Chat Completions response.

    Returns: [{id, name, arguments}]
    """
    try:
        obj = json.loads(resp_bytes.decode("utf-8", errors="ignore"))
    except Exception:
        return []

    if not isinstance(obj, dict):
        return []

    # Standard Chat Completions: choices[0].message.tool_calls
    choices = obj.get("choices")
    if isinstance(choices, list) and choices:
        first = choices[0] if isinstance(choices[0], dict) else {}
        msg = first.get("message", {}) if isinstance(first.get("message"), dict) else {}
        tool_calls = msg.get("tool_calls")
        if isinstance(tool_calls, list):
            calls = []
            for tc in tool_calls:
                if not isinstance(tc, dict):
                    continue
                fn = tc.get("function", {}) if isinstance(tc.get("function"), dict) else {}
                args_str = fn.get("arguments", "{}")
                try:
                    args = json.loads(args_str) if isinstance(args_str, str) else args_str
                except json.JSONDecodeError:
                    args = {}
                calls.append({
                    "id": tc.get("id", ""),
                    "name": fn.get("name", ""),
                    "arguments": args if isinstance(args, dict) else {},
                })
            return calls

    # Responses API: output[].type=="function_call"
    output = obj.get("output")
    if isinstance(output, list):
        calls = []
        for item in output:
            if not isinstance(item, dict):
                continue
            if item.get("type") == "function_call":
                args_str = item.get("arguments", "{}")
                try:
                    args = json.loads(args_str) if isinstance(args_str, str) else args_str
                except json.JSONDecodeError:
                    args = {}
                calls.append({
                    "id": item.get("call_id", item.get("id", "")),
                    "name": item.get("name", ""),
                    "arguments": args if isinstance(args, dict) else {},
                })
        return calls

    return []


def extract_tool_calls(provider_id: str, resp_bytes: bytes) -> List[Dict[str, Any]]:
    """Extract tool calls from provider response. Normalizes to common format.

    Returns: [{id, name, input}] — 'input' key normalized from 'arguments'.
    """
    if provider_id == "claude":
        return extract_tool_calls_claude(resp_bytes)
    calls = extract_tool_calls_openai(resp_bytes)
    # Normalize 'arguments' → 'input' for consistent downstream handling
    for call in calls:
        if "arguments" in call and "input" not in call:
            call["input"] = call.pop("arguments")
    return calls


# --- Tool result message builders ---

def build_tool_result_claude(tool_call_id: str, result: Dict[str, Any]) -> Dict[str, Any]:
    """Build Claude tool_result message block."""
    return {
        "type": "tool_result",
        "tool_use_id": tool_call_id,
        "content": json.dumps(result, ensure_ascii=False) if not isinstance(result, str) else result,
    }


def build_tool_result_openai(tool_call_id: str, result: Dict[str, Any]) -> Dict[str, Any]:
    """Build OpenAI tool result message."""
    return {
        "role": "tool",
        "tool_call_id": tool_call_id,
        "content": json.dumps(result, ensure_ascii=False) if not isinstance(result, str) else result,
    }


def build_tool_result(provider_id: str, tool_call_id: str, result: Dict[str, Any]) -> Dict[str, Any]:
    """Build provider-native tool result message."""
    if provider_id == "claude":
        return build_tool_result_claude(tool_call_id, result)
    return build_tool_result_openai(tool_call_id, result)

#!/usr/bin/env python3
"""Tiny stdio MCP wrapper for DeepSeek Delegate review packets."""

from __future__ import annotations

import json
import pathlib
import subprocess
import sys
import tempfile
from typing import Any, Callable


JSONRPC = "2.0"
TOOL_NAME = "deepseek_delegate_review"
SCRIPT_PATH = pathlib.Path(__file__).with_name("deepseek_delegate.py")


def response(request_id: Any, result: Any = None, error: dict | None = None) -> dict:
    payload: dict[str, Any] = {"jsonrpc": JSONRPC, "id": request_id}
    if error is not None:
        payload["error"] = error
    else:
        payload["result"] = result
    return payload


def helper_envelope(
    status: str,
    exit_code: int,
    warning: str,
    raw_stdout: str = "",
    raw_stderr: str = "",
) -> dict:
    return {
        "result": {
            "status": status,
            "driver": "mcp-wrapper",
            "exit_code": exit_code,
            "warnings": [warning],
        },
        "raw_stdout": raw_stdout,
        "raw_stderr": raw_stderr,
    }


def tool_schema() -> dict:
    return {
        "name": TOOL_NAME,
        "description": (
            "Run a bounded, read-only DeepSeek Delegate advisory review. "
            "Use for packet-local second opinions only; not for shell, edits, or full-repo work."
        ),
        "inputSchema": {
            "type": "object",
            "properties": {
                "task": {"type": "string", "description": "Bounded review task."},
                "mode": {
                    "type": "string",
                    "enum": ["answer", "audit", "calibration", "ablation", "review"],
                },
                "packet_profile": {
                    "type": "string",
                    "enum": ["default", "long-review", "weibo-ablation", "weibo-calibration"],
                },
                "context_text": {"type": "string", "description": "Inline packet text."},
                "context_files": {
                    "type": "array",
                    "items": {"type": "string"},
                    "description": "Packet files resolved under cwd.",
                },
                "cwd": {"type": "string", "description": "Workspace root for relative files."},
                "timeout_seconds": {"type": "integer", "minimum": 1},
                "max_context_chars": {"type": "integer", "minimum": 0},
                "chunk_chars": {"type": "integer", "minimum": 0},
                "structured_result": {"type": "boolean"},
            },
            "required": ["task"],
        },
    }


def validate_cwd(raw_cwd: Any) -> str | None:
    if raw_cwd in (None, ""):
        return None
    if not isinstance(raw_cwd, str):
        raise ValueError("cwd must be a string")
    cwd = pathlib.Path(raw_cwd).expanduser().resolve()
    if not cwd.exists() or not cwd.is_dir():
        raise ValueError(f"cwd is not a directory: {raw_cwd}")
    return str(cwd)


def validate_context_files(raw_files: Any, cwd: str | None) -> list[str]:
    if raw_files in (None, ""):
        return []
    if not isinstance(raw_files, list) or not all(isinstance(item, str) for item in raw_files):
        raise ValueError("context_files must be a string array")
    base = pathlib.Path(cwd).resolve() if cwd else pathlib.Path.cwd().resolve()
    normalized: list[str] = []
    for raw in raw_files:
        path = pathlib.Path(raw).expanduser()
        resolved = (base / path).resolve() if not path.is_absolute() else path.resolve()
        try:
            resolved.relative_to(base)
        except ValueError as exc:
            raise ValueError(f"context file must resolve under cwd: {raw}") from exc
        normalized.append(raw)
    return normalized


def build_delegate_payload(arguments: dict) -> tuple[dict, int]:
    if not isinstance(arguments, dict):
        raise ValueError("arguments must be an object")
    task = arguments.get("task")
    if not isinstance(task, str) or not task.strip():
        raise ValueError("task is required")
    cwd = validate_cwd(arguments.get("cwd"))
    context_files = validate_context_files(arguments.get("context_files"), cwd)
    context_text = arguments.get("context_text")
    if context_text is not None and not isinstance(context_text, str):
        raise ValueError("context_text must be a string")

    timeout_seconds = int(arguments.get("timeout_seconds", 180))
    payload = {
        "task": task,
        "mode": arguments.get("mode", "review"),
        "packet_profile": arguments.get("packet_profile", "default"),
        "context_text": context_text,
        "context_files": context_files,
        "cwd": cwd,
        "options": {
            "json_result": True,
            "structured_result": bool(arguments.get("structured_result", True)),
            "timeout_seconds": timeout_seconds,
        },
    }
    for field in ("max_context_chars", "chunk_chars"):
        if field in arguments:
            payload["options"][field] = int(arguments[field])
    return payload, timeout_seconds


def run_delegate_review(arguments: dict) -> dict:
    try:
        payload, timeout_seconds = build_delegate_payload(arguments)
    except Exception as exc:
        return helper_envelope("setup_error", 2, str(exc))

    tmp_path: pathlib.Path | None = None
    result: subprocess.CompletedProcess[str] | None = None
    try:
        with tempfile.NamedTemporaryFile(
            "w",
            encoding="utf-8",
            errors="replace",
            suffix=".deepseek-request.json",
            delete=False,
        ) as handle:
            json.dump(payload, handle, ensure_ascii=False)
            tmp_path = pathlib.Path(handle.name)

        result = subprocess.run(
            [sys.executable, str(SCRIPT_PATH), "--input-json", str(tmp_path), "--json-result"],
            cwd=payload.get("cwd") or None,
            text=True,
            encoding="utf-8",
            errors="replace",
            capture_output=True,
            timeout=max(60, timeout_seconds * 4),
        )
    except subprocess.TimeoutExpired as exc:
        return helper_envelope(
            "timeout",
            124,
            f"helper timed out after {max(60, timeout_seconds * 4)} seconds",
            str(exc.stdout or ""),
            str(exc.stderr or ""),
        )
    except OSError as exc:
        return helper_envelope("setup_error", 127, str(exc))
    finally:
        if tmp_path is not None:
            try:
                tmp_path.unlink()
            except OSError:
                pass

    if result is None:
        return helper_envelope("setup_error", 1, "helper did not start")
    output = result.stdout.strip()
    if output:
        try:
            return json.loads(output)
        except json.JSONDecodeError:
            pass
    return helper_envelope(
        "setup_error",
        result.returncode,
        "helper did not return a valid JSON envelope",
        result.stdout,
        result.stderr,
    )


def handle_request(
    request: dict,
    delegate_runner: Callable[[dict], dict] = run_delegate_review,
) -> dict | None:
    method = request.get("method")
    request_id = request.get("id")
    if method == "initialize":
        return response(
            request_id,
            {
                "protocolVersion": "2025-03-26",
                "capabilities": {"tools": {}},
                "serverInfo": {"name": "deepseek-delegate", "version": "2"},
            },
        )
    if method == "notifications/initialized":
        return None
    if method == "tools/list":
        return response(request_id, {"tools": [tool_schema()]})
    if method == "tools/call":
        params = request.get("params") or {}
        if params.get("name") != TOOL_NAME:
            return response(
                request_id,
                error={"code": -32601, "message": f"Unknown tool: {params.get('name')}"},
            )
        result = delegate_runner(params.get("arguments") or {})
        return response(
            request_id,
            {"content": [{"type": "text", "text": json.dumps(result, ensure_ascii=False)}]},
        )
    return response(request_id, error={"code": -32601, "message": f"Unsupported method: {method}"})


def main() -> int:
    for line in sys.stdin:
        line = line.strip()
        if not line:
            continue
        try:
            request = json.loads(line)
            reply = handle_request(request)
        except Exception as exc:
            request_id = request.get("id") if "request" in locals() and isinstance(request, dict) else None
            reply = response(request_id, error={"code": -32603, "message": str(exc)})
        if reply is not None:
            print(json.dumps(reply, ensure_ascii=False), flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

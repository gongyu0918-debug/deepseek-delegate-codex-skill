#!/usr/bin/env python3
"""Delegate a small bounded task to DeepSeek TUI with deterministic framing."""

from __future__ import annotations

import argparse
import json
import os
import pathlib
import queue
import re
import shutil
import subprocess
import sys
import tempfile
import threading
import time
from typing import Iterable


if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
if hasattr(sys.stderr, "reconfigure"):
    sys.stderr.reconfigure(encoding="utf-8", errors="replace")


REQUIRED_HEADINGS = [
    "Answer",
    "Evidence",
    "Uncertainty",
    "Suggested Codex Checks",
]

STRUCTURED_RESULT_REQUIRED_FIELDS = (
    "answer",
    "findings",
    "uncertainty",
    "suggested_codex_checks",
)
STRUCTURED_FINDING_REQUIRED_FIELDS = (
    "severity",
    "claim",
    "evidence",
    "codex_check",
)
STRUCTURED_SEVERITY_VALUES = ("low", "medium", "high")
STRUCTURED_RESULT_SCHEMA = """Return exactly one fenced JSON object and no other sections:
```json
{
  "answer": "Concise packet-local conclusion.",
  "findings": [
    {
      "severity": "low|medium|high",
      "claim": "Evidence-bound finding.",
      "evidence": "Packet quote, id, path, log line, or static code path.",
      "codex_check": "Exact local check Codex should perform."
    }
  ],
  "uncertainty": ["Missing context or assumptions."],
  "suggested_codex_checks": ["Commands, files, or evidence Codex should verify."]
}
```
Use an empty findings array only when there are no concrete findings.
"""


DRIVER_CHOICES = ("auto", "exec", "mcp")
BACKEND_TRANSPORT_CHOICES = ("auto", "exec-argv", "exec-file", "exec-stdin")
PROMPT_LIMITED_BACKENDS = ("exec-argv",)
DEFAULT_MCP_PROBE_TIMEOUT_SECONDS = 8
MCP_TOOL_NAME_KEYWORDS = ("delegate", "review")
MCP_TOOL_BLOCKLIST_KEYWORDS = ("shell", "exec", "command", "terminal", "process")
MCP_DELEGATE_INPUT_FIELDS = ("prompt", "task", "instructions")
MCP_PROTOCOL_VERSION = "2025-03-26"
INPUT_JSON_FIELD_MAP = {
    "task": "task",
    "mode": "mode",
    "packet_profile": "packet_profile",
    "profile": "packet_profile",
    "context_text": "context_text",
    "context_files": "context_file",
    "context_file": "context_file",
    "cwd": "cwd",
    "driver": "driver",
    "provider": "provider",
    "model": "model",
    "sandbox_mode": "sandbox_mode",
    "approval_policy": "approval_policy",
    "max_context_chars": "max_context_chars",
    "timeout_seconds": "timeout_seconds",
    "mcp_probe_timeout_seconds": "mcp_probe_timeout_seconds",
    "prompt_char_limit": "prompt_char_limit",
    "chunk_chars": "chunk_chars",
    "chunk_boundary_regex": "chunk_boundary_regex",
    "max_findings_per_chunk": "max_findings_per_chunk",
    "out": "out",
    "json_result": "json_result",
    "structured_result": "structured_result",
    "backend_transport": "backend_transport",
}
INT_FIELDS = {
    "max_context_chars",
    "timeout_seconds",
    "mcp_probe_timeout_seconds",
    "prompt_char_limit",
    "chunk_chars",
    "max_findings_per_chunk",
}
BOOL_FIELDS = {"json_result", "structured_result"}


class DelegateSetupError(Exception):
    """Local input or configuration error before a trustworthy delegate result exists."""

    exit_code = 2


class DelegateArgumentError(DelegateSetupError):
    """Argument parsing error that should be reported as setup_error."""

    def __init__(self, message: str, args_namespace: argparse.Namespace | None = None):
        super().__init__(message)
        self.args_namespace = args_namespace


class DelegateExecutableError(DelegateSetupError):
    """DeepSeek executable or transport setup failed."""

    exit_code = 127


class DelegateTimeoutError(Exception):
    """Delegate transport timed out."""


class DelegateArgumentParser(argparse.ArgumentParser):
    def error(self, message: str) -> None:
        raise DelegateArgumentError(message)


SENSITIVE_LITERAL_PATTERNS = [
    re.compile(r"\bsk-[A-Za-z0-9][A-Za-z0-9_-]{15,}\b"),
    re.compile(r"\bghp_[A-Za-z0-9_]{20,}\b"),
    re.compile(r"\bgithub_pat_[A-Za-z0-9_]{20,}\b", re.IGNORECASE),
    re.compile(r"\bglpat-[A-Za-z0-9_-]{20,}\b"),
    re.compile(r"\bxox[baprs]-[A-Za-z0-9-]{20,}\b"),
    re.compile(r"-----BEGIN [A-Z ]*PRIVATE KEY-----"),
]

DATABASE_URL_PATTERN = re.compile(
    r"\b[A-Z0-9_]*(DATABASE_URL|DB_URL|POSTGRES_URL|MYSQL_URL|REDIS_URL)[A-Z0-9_]*\s*[:=]\s*"
    r"[^ \t\r\n]*://[^ \t\r\n:/]+:([^ \t\r\n@]+)@[^ \t\r\n]+",
    re.IGNORECASE,
)
CREDENTIAL_ASSIGNMENT_PATTERN = re.compile(
    r"\b[A-Z0-9_]*("
    r"api[_-]?key|access[_-]?token|refresh[_-]?token|auth[_-]?token|"
    r"bearer[_-]?token|session[_-]?token|password|secret|cookie"
    r")[A-Z0-9_]*\s*[:=]\s*"
    r"(\"[^\"]+\"|'[^']+'|[^\s\"']+)",
    re.IGNORECASE,
)
AUTHORIZATION_PATTERN = re.compile(
    r"\bauthorization\s*:\s*(bearer|basic)\s+([A-Za-z0-9._~+/\-=]{8,})",
    re.IGNORECASE,
)
PLACEHOLDER_MARKERS = (
    "redacted",
    "example",
    "placeholder",
    "dummy",
    "sample",
    "test",
    "fake",
    "changeme",
    "your_",
    "your-",
    "xxx",
    "****",
    "<",
    ">",
    "...",
)


def strip_credential_value(value: str) -> str:
    return value.strip().strip(",;").strip("\"'")


def looks_like_placeholder(value: str) -> bool:
    normalized = strip_credential_value(value).strip()
    lower = normalized.lower()
    return (
        not normalized
        or lower in {"none", "null", "true", "false"}
        or any(marker in lower for marker in PLACEHOLDER_MARKERS)
        or normalized.startswith(("$", "%", "{", "[", "("))
    )


def looks_like_secret_value(value: str) -> bool:
    normalized = strip_credential_value(value)
    if looks_like_placeholder(normalized) or len(normalized) < 16:
        return False
    if not re.fullmatch(r"[A-Za-z0-9._~+/\-=]+", normalized):
        return False
    has_alpha = bool(re.search(r"[A-Za-z]", normalized))
    has_digit = bool(re.search(r"\d", normalized))
    has_symbol = bool(re.search(r"[._~+/\-=]", normalized))
    return has_alpha and has_digit and (has_symbol or len(set(normalized)) >= 10)


def credential_match_is_sensitive(match: re.Match[str]) -> bool:
    return looks_like_secret_value(match.group(2))


def database_url_match_is_sensitive(match: re.Match[str]) -> bool:
    password = match.group(2)
    return not looks_like_placeholder(password)


SENSITIVE_MATCHERS = [
    (pattern, lambda _match: True)
    for pattern in SENSITIVE_LITERAL_PATTERNS
] + [
    (
        DATABASE_URL_PATTERN,
        database_url_match_is_sensitive,
    ),
    (
        CREDENTIAL_ASSIGNMENT_PATTERN,
        credential_match_is_sensitive,
    ),
    (
        AUTHORIZATION_PATTERN,
        credential_match_is_sensitive,
    ),
]

MODE_GUIDANCE = {
    "answer": "Answer the bounded task concisely from the supplied packet only.",
    "audit": "Audit the supplied packet for risks, gaps, contradictions, or missed checks.",
    "calibration": "Compare supplied samples against the stated quality target; extract repeatable calibration signals.",
    "ablation": "Evaluate before/after or candidate variants; identify which changes improve or regress the target metric.",
    "review": "Review the supplied packet like a code reviewer; report only concrete, evidence-backed findings.",
}


PROFILE_DEFAULTS = {
    "default": {},
    "long-review": {
        "model": "deepseek-v4-pro",
        "max_context_chars": 100000,
        "prompt_char_limit": 24000,
        "chunk_chars": 18000,
        "timeout_seconds": 360,
        "max_findings_per_chunk": 8,
    },
}


CHOICE_FIELDS = {
    "mode": tuple(sorted(MODE_GUIDANCE)),
    "packet_profile": tuple(sorted(PROFILE_DEFAULTS)),
    "driver": DRIVER_CHOICES,
    "backend_transport": BACKEND_TRANSPORT_CHOICES,
}

def parse_args() -> argparse.Namespace:
    parser = DelegateArgumentParser(
        description="Call deepseek exec with a compact delegation packet."
    )
    parser.add_argument(
        "--input-json",
        default=None,
        help="Read delegate request JSON from this file, or '-' for stdin.",
    )
    parser.add_argument("--task", default=None, help="Bounded task for DeepSeek.")
    parser.add_argument(
        "--packet-profile",
        choices=sorted(PROFILE_DEFAULTS),
        default="default",
        help="Preset size and guidance profile for larger bounded review packets.",
    )
    parser.add_argument(
        "--mode",
        choices=sorted(MODE_GUIDANCE),
        default="answer",
        help="Delegation mode.",
    )
    parser.add_argument(
        "--context-file",
        action="append",
        default=[],
        help="File whose contents should be included in the packet. Repeat as needed.",
    )
    parser.add_argument(
        "--context-text",
        default=None,
        help=argparse.SUPPRESS,
    )
    parser.add_argument("--cwd", default=None, help="Working directory for deepseek exec.")
    parser.add_argument(
        "--driver",
        choices=DRIVER_CHOICES,
        default="exec",
        help="Agent-call transport. exec is the default; auto probes MCP first and falls back to exec.",
    )
    parser.add_argument(
        "--provider",
        default="deepseek",
        help="Provider to pass to deepseek before exec.",
    )
    parser.add_argument(
        "--model",
        default="deepseek-v4-pro",
        help="Model to pass to deepseek before exec.",
    )
    parser.add_argument(
        "--sandbox-mode",
        default="read-only",
        help="Sandbox mode for delegated CLI calls. Keep read-only unless deliberately testing.",
    )
    parser.add_argument(
        "--approval-policy",
        default="never",
        help="Approval policy for delegated CLI calls. Keep never for non-interactive Codex delegation.",
    )
    parser.add_argument(
        "--backend-transport",
        choices=BACKEND_TRANSPORT_CHOICES,
        default="auto",
        help=(
            "DeepSeek exec prompt transport. auto currently resolves to exec-argv; "
            "exec-file/stdin are reserved until deepseek exec exposes prompt-file or stdin support."
        ),
    )
    parser.add_argument(
        "--max-context-chars",
        type=int,
        default=24000,
        help="Maximum total characters to include from context files.",
    )
    parser.add_argument(
        "--timeout-seconds",
        type=int,
        default=180,
        help="Timeout for each deepseek exec call.",
    )
    parser.add_argument(
        "--mcp-probe-timeout-seconds",
        type=int,
        default=DEFAULT_MCP_PROBE_TIMEOUT_SECONDS,
        help="Short timeout for MCP tools/list probing before auto falls back to exec.",
    )
    parser.add_argument(
        "--prompt-char-limit",
        type=int,
        default=24000,
        help="Reject a single prompt above this many characters to avoid Windows CLI field limits.",
    )
    parser.add_argument(
        "--chunk-chars",
        type=int,
        default=0,
        help="Split long context into chunks of this size and call DeepSeek once per chunk.",
    )
    parser.add_argument(
        "--chunk-boundary-regex",
        default=None,
        help="Optional line regex that starts a new evidence block before chunk packing.",
    )
    parser.add_argument(
        "--max-findings-per-chunk",
        type=int,
        default=5,
        help="Guidance for chunked audits/reviews to keep each response concise.",
    )
    parser.add_argument("--out", default=None, help="Optional file for raw DeepSeek output.")
    parser.add_argument(
        "--json-result",
        action="store_true",
        help="Emit a structured request/result envelope as JSON instead of raw Markdown output.",
    )
    parser.add_argument(
        "--structured-result",
        action="store_true",
        help="Ask DeepSeek for a strict JSON findings object and validate it in the result envelope.",
    )
    args = parser.parse_args()
    args._input_json_fields = set()
    args.input_transport = "cli"
    args._resolved_backend_transport = None
    args._single_packet_attempted = False
    args._chunk_reason = None
    apply_input_json(args, parser)
    if not args.task:
        argument_error(args, "--task is required unless supplied by --input-json")
    apply_profile_defaults(args)
    validate_provider_model(args, parser)
    return args


def argument_error(args: argparse.Namespace, message: str) -> None:
    raise DelegateArgumentError(message, args)


def apply_input_json(args: argparse.Namespace, parser: argparse.ArgumentParser) -> None:
    if not args.input_json:
        return

    if args.input_json == "-":
        raw = sys.stdin.read()
        args.input_transport = "json-stdin"
    else:
        input_path = pathlib.Path(args.input_json).expanduser()
        try:
            raw = input_path.read_text(encoding="utf-8", errors="replace")
        except OSError as exc:
            argument_error(args, f"cannot read --input-json {args.input_json!r}: {exc}")
        args.input_transport = "json-file"

    try:
        payload = json.loads(raw)
    except json.JSONDecodeError as exc:
        argument_error(args, f"--input-json is not valid JSON: {exc.msg}")
    if not isinstance(payload, dict):
        argument_error(args, "--input-json root must be a JSON object")

    options = payload.get("options", {})
    if options is None:
        options = {}
    if not isinstance(options, dict):
        argument_error(args, "--input-json field 'options' must be an object when present")

    for source in (payload, options):
        for key, value in source.items():
            if key == "options":
                continue
            field = INPUT_JSON_FIELD_MAP.get(key)
            if field is None:
                continue
            apply_input_json_field(args, parser, field, value)


def apply_input_json_field(
    args: argparse.Namespace,
    parser: argparse.ArgumentParser,
    field: str,
    value: object,
) -> None:
    if field == "context_file":
        if value is None:
            normalized: list[str] = []
        elif isinstance(value, str):
            normalized = [value]
        elif isinstance(value, list) and all(isinstance(item, str) for item in value):
            normalized = list(value)
        else:
            argument_error(args, "--input-json context_files must be a string or string array")
        if not field_was_supplied_by_cli(field):
            args.context_file = normalized
            args._input_json_fields.add(field)
        return

    if field in BOOL_FIELDS and not isinstance(value, bool):
        argument_error(args, f"--input-json field {field!r} must be a boolean")
    if field in INT_FIELDS:
        if not isinstance(value, int) or isinstance(value, bool):
            argument_error(args, f"--input-json field {field!r} must be an integer")
    string_fields = {
        "task",
        "context_text",
        "cwd",
        "provider",
        "model",
        "sandbox_mode",
        "approval_policy",
        "chunk_boundary_regex",
        "out",
    }
    nullable_string_fields = {"context_text", "cwd", "chunk_boundary_regex", "out"}
    if field in string_fields:
        if value is None and field not in nullable_string_fields:
            argument_error(args, f"--input-json field {field!r} must be a string")
        if value is not None and not isinstance(value, str):
            argument_error(args, f"--input-json field {field!r} must be a string")
    choices = CHOICE_FIELDS.get(field)
    if choices and value not in choices:
        argument_error(
            args,
            f"--input-json field {field!r} must be one of: " + ", ".join(choices)
        )

    if not field_was_supplied_by_cli(field):
        setattr(args, field, value)
        args._input_json_fields.add(field)


def option_was_supplied(*names: str) -> bool:
    supplied = sys.argv[1:]
    return any(
        arg == name or arg.startswith(name + "=")
        for arg in supplied
        for name in names
    )


def field_was_supplied_by_cli(field: str) -> bool:
    return option_was_supplied("--" + field.replace("_", "-"))


def field_was_supplied(args: argparse.Namespace, field: str) -> bool:
    return field_was_supplied_by_cli(field) or field in getattr(args, "_input_json_fields", set())


def raw_argv_option_value(name: str) -> str | None:
    supplied = sys.argv[1:]
    for index, arg in enumerate(supplied):
        if arg == name and index + 1 < len(supplied):
            return supplied[index + 1]
        if arg.startswith(name + "="):
            return arg.split("=", 1)[1]
    return None


def fallback_args_for_setup_error(partial: argparse.Namespace | None = None) -> argparse.Namespace:
    if partial is not None:
        return partial
    return argparse.Namespace(
        input_json=raw_argv_option_value("--input-json"),
        input_transport="cli",
        task=None,
        mode="answer",
        packet_profile="default",
        model="deepseek-v4-pro",
        provider="deepseek",
        driver=raw_argv_option_value("--driver") or "exec",
        backend_transport=raw_argv_option_value("--backend-transport") or "auto",
        context_text=None,
        context_file=[],
        chunk_chars=0,
        chunk_boundary_regex=None,
        max_context_chars=24000,
        timeout_seconds=180,
        mcp_probe_timeout_seconds=DEFAULT_MCP_PROBE_TIMEOUT_SECONDS,
        prompt_char_limit=24000,
        max_findings_per_chunk=5,
        structured_result=option_was_supplied("--structured-result"),
        sandbox_mode="read-only",
        approval_policy="never",
        out=raw_argv_option_value("--out"),
        json_result=option_was_supplied("--json-result"),
        _input_json_fields=set(),
        _resolved_backend_transport=None,
        _single_packet_attempted=False,
        _chunk_reason=None,
    )


def apply_profile_defaults(args: argparse.Namespace) -> None:
    defaults = PROFILE_DEFAULTS.get(args.packet_profile, {})
    for field, value in defaults.items():
        if (
            field == "model"
            and field_was_supplied(args, "provider")
            and args.provider != "deepseek"
            and not field_was_supplied(args, "model")
        ):
            continue
        if not field_was_supplied(args, field):
            setattr(args, field, value)


def validate_provider_model(args: argparse.Namespace, parser: argparse.ArgumentParser) -> None:
    if args.provider != "deepseek" and args.model.startswith("deepseek-"):
        argument_error(
            args,
            "non-deepseek provider requires an explicit compatible --model; "
            f"got provider={args.provider!r} model={args.model!r}"
        )


def read_context_files(
    paths: Iterable[str],
    max_chars: int,
    base_dir: pathlib.Path | None = None,
) -> str:
    if max_chars < 0:
        raise DelegateSetupError("--max-context-chars must be non-negative")

    sections: list[str] = []
    remaining = max_chars

    for raw_path in paths:
        path = pathlib.Path(raw_path).expanduser()
        if base_dir and not path.is_absolute():
            path = base_dir / path
        if not path.exists():
            raise DelegateSetupError(f"context file not found: {raw_path}")
        if not path.is_file():
            raise DelegateSetupError(f"context path is not a file: {raw_path}")

        text = path.read_text(encoding="utf-8", errors="replace")
        reject_sensitive_text(text, f"context file {path}")
        original_len = len(text)
        if remaining <= 0:
            excerpt = ""
            truncated = True
        else:
            excerpt = text[:remaining]
            truncated = original_len > len(excerpt)
            remaining -= len(excerpt)

        marker = ""
        if truncated:
            marker = f"\n[truncated: original {original_len} chars]"

        sections.append(
            "\n".join(
                [
                    f"### Context file: {path}",
                    "```",
                    excerpt,
                    f"```{marker}",
                ]
            )
        )

    if not sections:
        return "No context files were provided."
    return "\n\n".join(sections)


def assemble_context(args: argparse.Namespace, base_dir: pathlib.Path | None = None) -> str:
    if args.max_context_chars < 0:
        raise DelegateSetupError("--max-context-chars must be non-negative")

    sections: list[str] = []
    remaining = args.max_context_chars
    if args.context_text is not None:
        reject_sensitive_text(args.context_text, "input-json context_text")
        original_len = len(args.context_text)
        if remaining <= 0:
            excerpt = ""
            truncated = True
        else:
            excerpt = args.context_text[:remaining]
            truncated = original_len > len(excerpt)
            remaining -= len(excerpt)
        marker = ""
        if truncated:
            marker = f"\n[truncated: original {original_len} chars]"
        sections.append(
            "\n".join(
                [
                    "### Context text: input-json",
                    "```",
                    excerpt,
                    f"```{marker}",
                ]
            )
        )

    if args.context_file:
        file_context = read_context_files(args.context_file, remaining, base_dir)
        if file_context != "No context files were provided.":
            sections.append(file_context)

    if not sections:
        return "No context files were provided."
    return "\n\n".join(sections)


def reject_sensitive_text(text: str, source: str) -> None:
    for pattern, is_sensitive in SENSITIVE_MATCHERS:
        for match in pattern.finditer(text):
            if not is_sensitive(match):
                continue
            raise DelegateSetupError(
                "sensitive-looking content detected in "
                f"{source}; refusing to pass it to DeepSeek Delegate"
            )


def build_prompt(args: argparse.Namespace, context: str) -> str:
    headings = "\n".join(f"## {heading}" for heading in REQUIRED_HEADINGS)
    chunk_guidance = ""
    if args.chunk_chars > 0:
        chunk_guidance = (
            f"- For chunked long text, report at most {args.max_findings_per_chunk} "
            "highest-value findings for this chunk.\n"
        )
    result_contract = (
        STRUCTURED_RESULT_SCHEMA.rstrip()
        if args.structured_result
        else "- Return exactly these Markdown headings, in this order:\n" + headings
    )
    return f"""You are a lightweight advisory subagent for Codex.

Mode: {args.mode}
Packet profile: {args.packet_profile}
Execution model: {args.model}
Mode guidance: {MODE_GUIDANCE[args.mode]}

Rules:
- Use only the task and context packet below.
- Do not modify files.
- Do not assume hidden Codex conversation context.
- Be concise and evidence-bound.
- Treat your findings as hypotheses until Codex reproduces or verifies them locally.
- For review findings, cite concrete packet evidence, a minimal reproduction, or a static code path.
- If evidence is insufficient, say so in Uncertainty.
- Keep the response compact enough to finish completely.
{chunk_guidance.rstrip()}
{result_contract}

Task:
{args.task}

Context packet:
{context}
"""


def split_text(text: str, chunk_chars: int, boundary_regex: str | None = None) -> list[str]:
    if chunk_chars <= 0 or len(text) <= chunk_chars:
        return [text]
    if boundary_regex:
        boundary_chunks = split_text_by_boundary(text, chunk_chars, boundary_regex)
        if boundary_chunks:
            return boundary_chunks

    chunks: list[str] = []
    start = 0
    while start < len(text):
        end = min(start + chunk_chars, len(text))
        if end < len(text):
            newline = text.rfind("\n", start, end)
            if newline > start + max(200, chunk_chars // 2):
                end = newline + 1
        chunks.append(text[start:end])
        start = end
    return chunks


def split_text_by_boundary(text: str, chunk_chars: int, boundary_regex: str) -> list[str]:
    pattern = re.compile(boundary_regex)
    saw_boundary = False
    blocks: list[str] = []
    current: list[str] = []

    for line in text.splitlines(keepends=True):
        if pattern.search(line) and current:
            saw_boundary = True
            blocks.append("".join(current))
            current = [line]
        else:
            if pattern.search(line):
                saw_boundary = True
            current.append(line)
    if current:
        blocks.append("".join(current))
    if len(blocks) <= 1:
        if not blocks:
            return []
        if saw_boundary and len(blocks[0]) > chunk_chars:
            raise DelegateSetupError(
                "single boundary block exceeds --chunk-chars; trim the block or raise "
                f"--chunk-chars without exceeding --prompt-char-limit (block chars={len(blocks[0])}, "
                f"limit={chunk_chars})"
            )
        if saw_boundary:
            return blocks
        return []

    chunks: list[str] = []
    current_chunk = ""
    for block in blocks:
        if len(block) > chunk_chars:
            raise DelegateSetupError(
                "single boundary block exceeds --chunk-chars; trim the block or raise "
                f"--chunk-chars without exceeding --prompt-char-limit (block chars={len(block)}, "
                f"limit={chunk_chars})"
            )
        if current_chunk and len(current_chunk) + len(block) > chunk_chars:
            chunks.append(current_chunk)
            current_chunk = block
        else:
            current_chunk += block
    if current_chunk:
        chunks.append(current_chunk)
    return chunks


def deepseek_executable() -> str | None:
    if os.name == "nt":
        appdata = os.environ.get("APPDATA")
        if appdata:
            downloads = pathlib.Path(appdata) / "npm" / "node_modules" / "deepseek-tui" / "bin" / "downloads"
            for name in ("deepseek.exe", "deepseek-tui.exe"):
                candidate = downloads / name
                if candidate.exists():
                    return str(candidate)
        for name in ("deepseek.exe", "deepseek-tui.exe", "deepseek.ps1", "deepseek.cmd", "deepseek"):
            found = shutil.which(name)
            if found:
                return found
        return None

    return shutil.which("deepseek")


def deepseek_command_invocation(command_args: list[str]) -> list[str]:
    found = deepseek_executable()
    if not found:
        return ["deepseek", *command_args]

    suffix = pathlib.Path(found).suffix.lower()
    if os.name == "nt":
        if suffix == ".ps1":
            return [
                "powershell.exe",
                "-NoProfile",
                "-ExecutionPolicy",
                "Bypass",
                "-File",
                found,
                *command_args,
            ]
        if suffix in {".cmd", ".bat"}:
            command_line = subprocess.list2cmdline([found, *command_args])
            return ["cmd.exe", "/d", "/s", "/c", command_line]

    return [found, *command_args]


def deepseek_invocation(
    args: argparse.Namespace,
    prompt: str,
    backend_transport: str = "exec-argv",
    prompt_path: pathlib.Path | None = None,
) -> list[str]:
    common_args = [
        "--provider",
        args.provider,
        "--model",
        args.model,
        "--sandbox-mode",
        args.sandbox_mode,
        "--approval-policy",
        args.approval_policy,
    ]
    if backend_transport == "exec-file":
        if prompt_path is None:
            raise DelegateSetupError("exec-file backend requires a prompt file path")
        exec_args = ["exec", "--prompt-file", str(prompt_path)]
    elif backend_transport == "exec-stdin":
        exec_args = ["exec", "--stdin"]
    else:
        exec_args = ["exec", prompt]

    return deepseek_command_invocation([*common_args, *exec_args])


def deepseek_mcp_invocation() -> list[str]:
    return deepseek_command_invocation(["mcp-server"])


def deepseek_exec_supports_transport(backend_transport: str) -> bool:
    if backend_transport == "exec-argv":
        return True
    invocation = deepseek_command_invocation(["exec", "--help"])
    try:
        result = subprocess.run(
            invocation,
            text=True,
            encoding="utf-8",
            errors="replace",
            capture_output=True,
            timeout=8,
        )
    except (OSError, subprocess.TimeoutExpired):
        return False
    help_text = result.stdout + "\n" + result.stderr
    if backend_transport == "exec-file":
        return "--prompt-file" in help_text or "--file" in help_text
    if backend_transport == "exec-stdin":
        return "--stdin" in help_text or "-f, --file" in help_text
    return False


def resolve_backend_transport(args: argparse.Namespace, driver: str) -> str:
    if driver == "mcp":
        if args.backend_transport not in {"auto", "exec-argv"}:
            raise DelegateSetupError(
                "--backend-transport applies only to the exec driver, not --driver mcp"
            )
        return "mcp-stdio"

    requested = args.backend_transport
    if requested == "auto":
        return "exec-argv"
    if requested == "exec-argv":
        return "exec-argv"
    if requested in {"exec-file", "exec-stdin"}:
        if deepseek_exec_supports_transport(requested):
            return requested
        raise DelegateSetupError(
            f"backend transport {requested} is reserved, but this deepseek exec "
            "does not advertise prompt-file/stdin support"
        )
    raise DelegateSetupError(f"unknown backend transport: {requested}")


def backend_prompt_has_command_limit(backend_transport: str) -> bool:
    return backend_transport in PROMPT_LIMITED_BACKENDS


def backend_allows_single_packet(args: argparse.Namespace, prompt: str, backend_transport: str) -> bool:
    if not backend_prompt_has_command_limit(backend_transport):
        return True
    return len(prompt) <= args.prompt_char_limit


def mcp_send(proc: subprocess.Popen[str], payload: dict) -> None:
    if not proc.stdin:
        raise RuntimeError("MCP server stdin is unavailable")
    proc.stdin.write(json.dumps(payload, separators=(",", ":")) + "\n")
    proc.stdin.flush()


def mcp_read(proc: subprocess.Popen[str], timeout_seconds: int) -> dict:
    if not proc.stdout:
        raise RuntimeError("MCP server stdout is unavailable")
    lines: queue.Queue[str] = queue.Queue(maxsize=1)

    def read_line() -> None:
        try:
            lines.put(proc.stdout.readline())
        except Exception as exc:
            lines.put(f'{{"jsonrpc":"2.0","error":{{"message":{json.dumps(str(exc))}}}}}')

    threading.Thread(target=read_line, daemon=True).start()
    try:
        line = lines.get(timeout=timeout_seconds)
    except queue.Empty as exc:
        kill_process(proc)
        raise DelegateTimeoutError("MCP server did not return a response") from exc
    if not line:
        stderr = ""
        if proc.stderr:
            try:
                stderr = proc.stderr.read(1000)
            except OSError:
                stderr = ""
        kill_process(proc)
        raise DelegateTimeoutError(f"MCP server did not return a response. {stderr}".strip())
    return json.loads(line)


def kill_process(proc: subprocess.Popen[str]) -> None:
    if proc.poll() is not None:
        return
    try:
        proc.kill()
    except OSError:
        return
    try:
        proc.wait(timeout=2)
    except (OSError, subprocess.TimeoutExpired):
        return


def mcp_request(
    proc: subprocess.Popen[str],
    request_id: int,
    method: str,
    params: dict | None = None,
    timeout_seconds: int = 8,
) -> dict:
    payload = {"jsonrpc": "2.0", "id": request_id, "method": method}
    if params is not None:
        payload["params"] = params
    mcp_send(proc, payload)
    response = mcp_read(proc, timeout_seconds)
    if "error" in response:
        raise RuntimeError(f"MCP {method} failed: {response['error']}")
    return response.get("result", {})


def start_mcp_server(cwd: str | None) -> subprocess.Popen[str]:
    return subprocess.Popen(
        deepseek_mcp_invocation(),
        cwd=cwd,
        stdin=subprocess.PIPE,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
        encoding="utf-8",
        errors="replace",
    )


def list_mcp_tools(cwd: str | None = None, timeout_seconds: int = 8) -> list[dict]:
    proc = start_mcp_server(cwd)
    try:
        mcp_request(
            proc,
            1,
            "initialize",
            {
                "protocolVersion": MCP_PROTOCOL_VERSION,
                "capabilities": {},
                "clientInfo": {"name": "codex-deepseek-delegate", "version": "1"},
            },
            timeout_seconds=timeout_seconds,
        )
        result = mcp_request(proc, 2, "tools/list", {}, timeout_seconds=timeout_seconds)
        tools = result.get("tools", [])
        if not isinstance(tools, list):
            return []
        return [tool for tool in tools if isinstance(tool, dict)]
    finally:
        kill_process(proc)


def select_mcp_delegate_tool(tools: list[dict]) -> dict | None:
    for tool in tools:
        name = str(tool.get("name", "")).lower()
        if any(blocked in name for blocked in MCP_TOOL_BLOCKLIST_KEYWORDS):
            continue
        if not any(keyword in name for keyword in MCP_TOOL_NAME_KEYWORDS):
            continue
        if not mcp_tool_accepts_delegate_input(tool):
            continue
        return tool
    return None


def mcp_tool_accepts_delegate_input(tool: dict) -> bool:
    schema = tool.get("inputSchema") or tool.get("input_schema") or {}
    if not isinstance(schema, dict):
        return False
    properties = schema.get("properties", {})
    if not isinstance(properties, dict):
        return False
    return any(field in properties for field in MCP_DELEGATE_INPUT_FIELDS)


def resolve_driver(args: argparse.Namespace, cwd: str | None) -> tuple[str, list[str], dict | None]:
    if args.driver == "exec":
        return "exec", [], None

    try:
        tool = select_mcp_delegate_tool(list_mcp_tools(cwd, args.mcp_probe_timeout_seconds))
    except Exception as exc:
        if args.driver == "mcp":
            raise RuntimeError(f"requested mcp driver but MCP probe failed: {exc}") from exc
        return "exec", [f"auto driver fell back to exec because MCP probe failed: {exc}"], None

    if tool:
        return "mcp", [], tool

    if args.driver == "mcp":
        raise RuntimeError("requested mcp driver but no delegate/review MCP tool is exposed")
    return "exec", ["auto driver fell back to exec because MCP tools/list exposed no delegate/review tool"], None


def mcp_tool_arguments(tool: dict, args: argparse.Namespace, prompt: str, cwd: str | None) -> dict:
    arguments: dict[str, object] = {}
    schema = tool.get("inputSchema") or tool.get("input_schema") or {}
    properties = schema.get("properties", {}) if isinstance(schema, dict) else {}
    if not isinstance(properties, dict):
        properties = {}

    def accepts(name: str) -> bool:
        return not properties or name in properties

    full_prompt_field = next(
        (field for field in MCP_DELEGATE_INPUT_FIELDS if accepts(field)),
        "prompt",
    )
    arguments[full_prompt_field] = prompt
    if accepts("prompt"):
        arguments["prompt"] = prompt
    if accepts("task"):
        arguments["task"] = args.task if full_prompt_field != "task" else prompt
    if accepts("instructions"):
        arguments["instructions"] = (
            prompt if full_prompt_field == "instructions" else args.task
        )
    if accepts("mode"):
        arguments["mode"] = args.mode
    if accepts("packet_profile"):
        arguments["packet_profile"] = args.packet_profile
    if accepts("model"):
        arguments["model"] = args.model
    if accepts("provider"):
        arguments["provider"] = args.provider
    if accepts("cwd"):
        arguments["cwd"] = cwd
    if accepts("structured_result"):
        arguments["structured_result"] = args.structured_result
    if accepts("json_result"):
        arguments["json_result"] = args.json_result
    if accepts("timeout_seconds"):
        arguments["timeout_seconds"] = args.timeout_seconds
    if accepts("max_context_chars"):
        arguments["max_context_chars"] = args.max_context_chars
    if accepts("chunk_chars"):
        arguments["chunk_chars"] = args.chunk_chars
    if accepts("chunk_boundary_regex"):
        arguments["chunk_boundary_regex"] = args.chunk_boundary_regex
    if accepts("max_findings_per_chunk"):
        arguments["max_findings_per_chunk"] = args.max_findings_per_chunk
    return arguments


def extract_mcp_text(result: dict) -> str:
    content = result.get("content")
    if isinstance(content, list):
        parts: list[str] = []
        for item in content:
            if isinstance(item, dict) and isinstance(item.get("text"), str):
                parts.append(item["text"])
        if parts:
            return "\n".join(parts)
    if isinstance(result.get("text"), str):
        return result["text"]
    return json.dumps(result, ensure_ascii=False, indent=2)


def exit_code_from_status(status: object) -> int:
    if status == "ok":
        return 0
    if status == "partial":
        return 3
    if status == "timeout":
        return 124
    if status == "setup_error":
        return 2
    if status == "error":
        return 1
    return 1


def normalize_mcp_delegate_output(args: argparse.Namespace, output: str) -> tuple[int, str]:
    try:
        value = json.loads(output)
    except json.JSONDecodeError:
        return 0, output
    if not isinstance(value, dict):
        return 0, output
    result = value.get("result")
    if not isinstance(result, dict):
        return 0, output

    exit_code = result.get("exit_code")
    if not isinstance(exit_code, int):
        exit_code = exit_code_from_status(result.get("status"))

    chunks = result.get("chunks")
    if (
        args.structured_result
        and result.get("status") == "ok"
        and isinstance(chunks, list)
        and len(chunks) == 1
        and isinstance(chunks[0], dict)
        and chunks[0].get("structured_ok") is True
        and isinstance(chunks[0].get("structured_result"), dict)
    ):
        return exit_code, json.dumps(chunks[0]["structured_result"], ensure_ascii=False)
    return exit_code, output


def call_deepseek_mcp_driver(
    args: argparse.Namespace,
    prompt: str,
    cwd: str | None,
    tool: dict | None,
) -> tuple[int, str]:
    if tool is None:
        raise RuntimeError("MCP driver selected without an MCP delegate tool")
    proc = start_mcp_server(cwd)
    try:
        mcp_request(
            proc,
            1,
            "initialize",
            {
                "protocolVersion": MCP_PROTOCOL_VERSION,
                "capabilities": {},
                "clientInfo": {"name": "codex-deepseek-delegate", "version": "1"},
            },
        )
        result = mcp_request(
            proc,
            2,
            "tools/call",
            {"name": tool.get("name"), "arguments": mcp_tool_arguments(tool, args, prompt, cwd)},
            timeout_seconds=args.timeout_seconds,
        )
        return normalize_mcp_delegate_output(args, extract_mcp_text(result))
    finally:
        kill_process(proc)


def write_output(path: str | None, text: str, cwd: str | None = None) -> None:
    if not path:
        return
    output_path = pathlib.Path(path).expanduser()
    if cwd and not output_path.is_absolute():
        output_path = pathlib.Path(cwd).expanduser() / output_path
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(text, encoding="utf-8")


def write_error_output(
    args: argparse.Namespace,
    text: str,
    cwd: str | None,
    cwd_valid: bool,
) -> None:
    if not args.out:
        return
    output_path = pathlib.Path(args.out).expanduser()
    if cwd_valid or output_path.is_absolute():
        write_output(args.out, text, cwd if cwd_valid else None)


def missing_required_headings(output: str) -> list[str]:
    ordered: list[str] = []
    in_fence = False
    for raw_line in output.splitlines():
        stripped = raw_line.strip()
        if stripped.startswith("```") or stripped.startswith("~~~"):
            in_fence = not in_fence
            continue
        if in_fence:
            continue
        match = re.match(r"^##\s+(.+?)\s*$", raw_line.rstrip())
        if match:
            heading = match.group(1).strip()
            if heading in REQUIRED_HEADINGS:
                ordered.append(heading)
    for index, heading in enumerate(REQUIRED_HEADINGS):
        if index >= len(ordered) or ordered[index] != heading:
            return REQUIRED_HEADINGS[index:]
    return []


def extract_json_object(text: str) -> str | None:
    fenced = re.search(r"```(?:json)?\s*(.*?)\s*```", text, re.DOTALL | re.IGNORECASE)
    if fenced:
        fenced_text = fenced.group(1).strip()
        if fenced_text:
            return fenced_text

    start = text.find("{")
    if start < 0:
        return None

    depth = 0
    in_string = False
    escaped = False
    for index in range(start, len(text)):
        char = text[index]
        if in_string:
            if escaped:
                escaped = False
            elif char == "\\":
                escaped = True
            elif char == '"':
                in_string = False
            continue
        if char == '"':
            in_string = True
        elif char == "{":
            depth += 1
        elif char == "}":
            depth -= 1
            if depth == 0:
                return text[start : index + 1]
    return None


def validate_structured_result(value: object) -> list[str]:
    errors: list[str] = []
    if not isinstance(value, dict):
        return ["structured result must be a JSON object"]

    for field in STRUCTURED_RESULT_REQUIRED_FIELDS:
        if field not in value:
            errors.append(f"missing root field: {field}")

    if "answer" in value and not isinstance(value["answer"], str):
        errors.append("answer must be a string")
    if "findings" in value and not isinstance(value["findings"], list):
        errors.append("findings must be a list")
    if "uncertainty" in value and not isinstance(value["uncertainty"], list):
        errors.append("uncertainty must be a list")
    if "suggested_codex_checks" in value and not isinstance(value["suggested_codex_checks"], list):
        errors.append("suggested_codex_checks must be a list")
    if isinstance(value.get("uncertainty"), list):
        for index, item in enumerate(value["uncertainty"], start=1):
            if not isinstance(item, str):
                errors.append(f"uncertainty {index} must be a string")
    if isinstance(value.get("suggested_codex_checks"), list):
        for index, item in enumerate(value["suggested_codex_checks"], start=1):
            if not isinstance(item, str):
                errors.append(f"suggested_codex_checks {index} must be a string")

    findings = value.get("findings") if isinstance(value, dict) else None
    if isinstance(findings, list):
        for index, finding in enumerate(findings, start=1):
            if not isinstance(finding, dict):
                errors.append(f"finding {index} must be an object")
                continue
            for field in STRUCTURED_FINDING_REQUIRED_FIELDS:
                if field not in finding:
                    errors.append(f"finding {index} missing field: {field}")
                elif not isinstance(finding[field], str):
                    errors.append(f"finding {index} field {field} must be a string")
            severity = finding.get("severity")
            if isinstance(severity, str) and severity not in STRUCTURED_SEVERITY_VALUES:
                errors.append(
                    f"finding {index} severity must be one of: "
                    + ", ".join(STRUCTURED_SEVERITY_VALUES)
                )
    return errors


def parse_structured_result(output: str) -> tuple[dict | None, list[str]]:
    candidate = extract_json_object(output)
    if candidate is None:
        return None, ["no JSON object found"]
    try:
        value = json.loads(candidate)
    except json.JSONDecodeError as exc:
        return None, [f"invalid JSON: {exc.msg}"]
    errors = validate_structured_result(value)
    if errors:
        return value if isinstance(value, dict) else None, errors
    return value, []


def validate_delegate_prompt(
    args: argparse.Namespace,
    prompt: str,
    backend_transport: str,
) -> None:
    if backend_prompt_has_command_limit(backend_transport) and len(prompt) > args.prompt_char_limit:
        raise DelegateSetupError(
            f"prompt chars={len(prompt)} exceeds --prompt-char-limit={args.prompt_char_limit}; "
            "lower --chunk-chars or reduce --max-context-chars"
        )
    reject_sensitive_text(prompt, "delegation prompt")


def call_deepseek_exec_driver(
    args: argparse.Namespace,
    prompt: str,
    cwd: str | None,
    timeout_seconds: int,
    backend_transport: str,
) -> tuple[int, str]:
    prompt_path: pathlib.Path | None = None
    run_input: str | None = None
    try:
        if backend_transport == "exec-file":
            with tempfile.NamedTemporaryFile(
                "w",
                encoding="utf-8",
                errors="replace",
                suffix=".deepseek-prompt.txt",
                delete=False,
            ) as handle:
                handle.write(prompt)
                prompt_path = pathlib.Path(handle.name)
        elif backend_transport == "exec-stdin":
            run_input = prompt

        invocation = deepseek_invocation(
            args,
            prompt if backend_transport == "exec-argv" else "",
            backend_transport,
            prompt_path,
        )
        if os.name == "nt" and len(subprocess.list2cmdline(invocation)) > windows_command_limit(invocation):
            raise DelegateSetupError(
                "estimated Windows command line exceeds conservative Windows limit; "
                "lower --chunk-chars, shorten --task, or reduce --max-context-chars"
            )
        result = subprocess.run(
            invocation,
            cwd=cwd,
            input=run_input,
            text=True,
            encoding="utf-8",
            errors="replace",
            capture_output=True,
            timeout=timeout_seconds,
        )
    finally:
        if prompt_path is not None:
            try:
                prompt_path.unlink()
            except OSError:
                pass
    output = result.stdout
    if result.stderr:
        output = output.rstrip() + "\n\n[stderr]\n" + result.stderr
    return result.returncode, output


def call_deepseek_with_metadata(
    args: argparse.Namespace,
    prompt: str,
    cwd: str | None,
    timeout_seconds: int,
    driver: str,
    backend_transport: str,
    mcp_tool: dict | None = None,
) -> dict:
    validate_delegate_prompt(args, prompt, backend_transport)
    start = time.monotonic()
    warnings: list[str] = []
    if driver == "mcp":
        code, output = call_deepseek_mcp_driver(args, prompt, cwd, mcp_tool)
    else:
        code, output = call_deepseek_exec_driver(
            args,
            prompt,
            cwd,
            timeout_seconds,
            backend_transport,
        )
    duration = time.monotonic() - start
    return {
        "driver": driver,
        "backend_transport": backend_transport,
        "exit_code": code,
        "output": output,
        "duration_seconds": round(duration, 3),
        "warnings": warnings,
    }


def call_deepseek(
    args: argparse.Namespace,
    prompt: str,
    cwd: str | None,
    timeout_seconds: int,
) -> tuple[int, str]:
    call = call_deepseek_with_metadata(
        args,
        prompt,
        cwd,
        timeout_seconds,
        "exec",
        resolve_backend_transport(args, "exec"),
    )
    return int(call["exit_code"]), str(call["output"])


def windows_command_limit(invocation: list[str]) -> int:
    if not invocation:
        return 30000
    executable = pathlib.Path(invocation[0]).name.lower()
    if executable == "cmd.exe":
        return 7800
    return 30000


def request_envelope(args: argparse.Namespace, cwd: str | None) -> dict:
    return {
        "task": args.task,
        "mode": args.mode,
        "profile": args.packet_profile,
        "input_transport": getattr(args, "input_transport", "cli"),
        "provider": args.provider,
        "model": args.model,
        "cwd": cwd,
        "context_files": list(args.context_file),
        "driver": args.driver,
        "backend_transport_request": getattr(args, "backend_transport", "auto"),
        "mcp_probe_timeout_seconds": getattr(
            args,
            "mcp_probe_timeout_seconds",
            DEFAULT_MCP_PROBE_TIMEOUT_SECONDS,
        ),
        "chunk_policy": {
            "chunk_chars": args.chunk_chars,
            "chunk_boundary_regex": args.chunk_boundary_regex,
            "max_context_chars": args.max_context_chars,
            "prompt_char_limit": args.prompt_char_limit,
            "max_findings_per_chunk": args.max_findings_per_chunk,
            "structured_result": args.structured_result,
        },
        "safety_policy": {
            "sandbox_mode": args.sandbox_mode,
            "approval_policy": args.approval_policy,
            "sensitive_guard": "fail-closed before invocation",
            "required_headings": REQUIRED_HEADINGS,
        },
    }


def make_result_envelope(
    args: argparse.Namespace,
    cwd: str | None,
    cwd_valid: bool,
    status: str,
    driver: str | None,
    exit_code: int,
    chunks: list[dict],
    warnings: list[str],
    started_at: float,
) -> dict:
    headings_ok = bool(chunks) and all(chunk.get("headings_ok") for chunk in chunks)
    return {
        "request": request_envelope(args, cwd),
        "result": {
            "status": status,
            "driver": driver or args.driver,
            "input_transport": getattr(args, "input_transport", "cli"),
            "backend_transport": getattr(args, "_resolved_backend_transport", None),
            "single_packet_attempted": bool(getattr(args, "_single_packet_attempted", False)),
            "chunk_reason": getattr(args, "_chunk_reason", None),
            "model": args.model,
            "chunks": chunks,
            "exit_code": exit_code,
            "headings_ok": headings_ok,
            "warnings": warnings,
            "duration_seconds": round(time.monotonic() - started_at, 3),
            "output_path": output_path_for_envelope(args.out, cwd, cwd_valid),
        },
    }


def resolve_output_path(path: str | None, cwd: str | None = None) -> str | None:
    if not path:
        return None
    output_path = pathlib.Path(path).expanduser()
    if cwd and not output_path.is_absolute():
        output_path = pathlib.Path(cwd).expanduser() / output_path
    return str(output_path)


def output_path_for_envelope(path: str | None, cwd: str | None, cwd_valid: bool) -> str | None:
    if not path:
        return None
    output_path = pathlib.Path(path).expanduser()
    if not cwd_valid and not output_path.is_absolute():
        return None
    if not output_path.is_absolute():
        base = pathlib.Path(cwd).expanduser() if cwd_valid and cwd else pathlib.Path.cwd()
        output_path = base / output_path
        return str(output_path)
    return resolve_output_path(path, cwd if cwd_valid else None)


def chunk_result(
    chunk_id: str,
    call: dict,
    missing: list[str],
    warnings: list[str],
    structured_result: dict | None = None,
    structured_errors: list[str] | None = None,
    headings_checked: bool = True,
) -> dict:
    exit_code = int(call["exit_code"])
    if missing is None:
        missing = list(REQUIRED_HEADINGS)
    headings_ok = not missing
    structured_errors = structured_errors or []
    structured_ok = not structured_errors
    status = "ok"
    if missing:
        status = "partial"
    if structured_errors:
        status = "partial"
    if exit_code != 0:
        status = "error"
    return {
        "chunk_id": chunk_id,
        "status": status,
        "driver": call["driver"],
        "backend_transport": call.get("backend_transport"),
        "exit_code": exit_code,
        "headings_checked": headings_checked,
        "headings_ok": headings_ok,
        "missing_headings": missing,
        "structured_ok": structured_ok,
        "structured_errors": structured_errors,
        "structured_result": structured_result,
        "finding_count": len(structured_result.get("findings", [])) if structured_result else 0,
        "warnings": warnings,
        "duration_seconds": call["duration_seconds"],
        "output_chars": len(str(call["output"])),
    }


def final_status(exit_code: int, chunks: list[dict]) -> str:
    if exit_code == 124:
        return "timeout"
    if exit_code in {1, 2, 127} and not chunks:
        return "setup_error"
    if any(chunk.get("status") == "partial" for chunk in chunks):
        return "partial"
    if exit_code == 0:
        return "ok"
    return "error"


def emit_result(args: argparse.Namespace, output: str, envelope: dict) -> None:
    if args.json_result:
        print(json.dumps(envelope, ensure_ascii=False, indent=2))
    elif output:
        print(output, end="" if output.endswith("\n") else "\n")


def main() -> int:
    started_at = time.monotonic()
    try:
        args = parse_args()
    except DelegateArgumentError as exc:
        args = fallback_args_for_setup_error(getattr(exc, "args_namespace", None))
        output = f"DeepSeek delegation setup failed: {exc}\n"
        envelope = make_result_envelope(
            args,
            None,
            False,
            "setup_error",
            None,
            int(getattr(exc, "exit_code", 2)),
            [],
            [str(exc)],
            started_at,
        )
        if args.json_result:
            emit_result(args, output, envelope)
        else:
            print(output, file=sys.stderr)
        return int(getattr(exc, "exit_code", 2))
    cwd = None
    cwd_valid = False
    selected_driver: str | None = None
    mcp_tool: dict | None = None
    chunks_meta: list[dict] = []
    warnings: list[str] = []

    try:
        if args.cwd:
            cwd_path = pathlib.Path(args.cwd).expanduser()
            if not cwd_path.exists():
                raise DelegateSetupError(f"--cwd does not exist: {args.cwd}")
            if not cwd_path.is_dir():
                raise DelegateSetupError(f"--cwd is not a directory: {args.cwd}")
            cwd = str(cwd_path)
            cwd_valid = True
        else:
            cwd = None
            cwd_valid = True
        base_dir = pathlib.Path(cwd) if cwd else None
        reject_sensitive_text(args.task, "task")
        context = assemble_context(args, base_dir)
        reject_sensitive_text(context, "assembled context packet")
        selected_driver, driver_warnings, mcp_tool = resolve_driver(args, cwd)
        warnings.extend(driver_warnings)
        backend_transport = resolve_backend_transport(args, selected_driver)
        args._resolved_backend_transport = backend_transport
        prompt = build_prompt(args, context)
        if not backend_allows_single_packet(args, prompt, backend_transport):
            args._single_packet_attempted = False
            args._chunk_reason = (
                f"full prompt chars={len(prompt)} exceeds prompt_char_limit="
                f"{args.prompt_char_limit} for backend_transport={backend_transport}"
            )
            if args.chunk_chars <= 0:
                raise DelegateSetupError(
                    args._chunk_reason + "; enable --chunk-chars or reduce the packet"
                )
            chunks = split_text(context, args.chunk_chars, args.chunk_boundary_regex)
            outputs: list[str] = []
            worst_code = 0
            for index, chunk in enumerate(chunks, start=1):
                chunk_id = f"chunk-{index:03d}-of-{len(chunks):03d}"
                chunk_context = (
                    f"Chunk ID: {chunk_id}.\n"
                    f"Chunk {index} of {len(chunks)}. Focus only on this chunk; "
                    "do not claim full-document completeness or global repository coverage.\n\n"
                    f"{chunk}"
                )
                prompt = build_prompt(args, chunk_context)
                call = call_deepseek_with_metadata(
                    args,
                    prompt,
                    cwd,
                    args.timeout_seconds,
                    selected_driver,
                    backend_transport,
                    mcp_tool,
                )
                code = int(call["exit_code"])
                chunk_output = str(call["output"])
                worst_code = code if code != 0 else worst_code
                chunk_warnings = list(call["warnings"])
                structured_result = None
                structured_errors: list[str] = []
                if args.structured_result:
                    missing = []
                    structured_result, structured_errors = parse_structured_result(chunk_output)
                    if structured_errors:
                        worst_code = worst_code or 3
                        chunk_warnings.append(
                            "structured result errors: " + "; ".join(structured_errors)
                        )
                        chunk_output = (
                            chunk_output.rstrip()
                            + "\n\n[delegate warning]\n"
                            + "Structured result errors: "
                            + "; ".join(structured_errors)
                            + ". Treat this chunk as partial; retry with a smaller packet "
                            + "or clarify the JSON contract.\n"
                        )
                else:
                    missing = missing_required_headings(chunk_output)
                if missing:
                    worst_code = worst_code or 3
                    chunk_warnings.append(
                        "missing required headings: " + ", ".join(missing)
                    )
                    chunk_output = (
                        chunk_output.rstrip()
                        + "\n\n[delegate warning]\n"
                        + "Missing required headings: "
                        + ", ".join(missing)
                        + ". Treat this chunk as partial; retry with smaller --chunk-chars "
                        + "or lower --max-findings-per-chunk if needed.\n"
                    )
                chunks_meta.append(
                    chunk_result(
                        chunk_id,
                        call,
                        missing,
                        chunk_warnings,
                        structured_result,
                        structured_errors,
                        not args.structured_result,
                    )
                )
                outputs.append(f"# DeepSeek {chunk_id}\n\n{chunk_output}")
            output = "\n\n---\n\n".join(outputs)
            write_output(args.out, output, cwd)
            envelope = make_result_envelope(
                args,
                cwd,
                cwd_valid,
                final_status(worst_code, chunks_meta),
                selected_driver,
                worst_code,
                chunks_meta,
                warnings,
                started_at,
            )
            emit_result(args, output, envelope)
            return worst_code

        args._single_packet_attempted = True
        args._chunk_reason = None
        call = call_deepseek_with_metadata(
            args,
            prompt,
            cwd,
            args.timeout_seconds,
            selected_driver,
            backend_transport,
            mcp_tool,
        )
        returncode = int(call["exit_code"])
        output = str(call["output"])
        chunk_warnings = list(call["warnings"])
        structured_result = None
        structured_errors: list[str] = []
        if args.structured_result:
            missing = []
            structured_result, structured_errors = parse_structured_result(output)
            if structured_errors and returncode == 0:
                returncode = 3
                chunk_warnings.append(
                    "structured result errors: " + "; ".join(structured_errors)
                )
                output = (
                    output.rstrip()
                    + "\n\n[delegate warning]\n"
                    + "Structured result errors: "
                    + "; ".join(structured_errors)
                    + ". Treat this output as partial or malformed.\n"
                )
        else:
            missing = missing_required_headings(output)
        if missing and returncode == 0:
            returncode = 3
            chunk_warnings.append("missing required headings: " + ", ".join(missing))
            output = (
                output.rstrip()
                + "\n\n[delegate warning]\n"
                + "Missing required headings: "
                + ", ".join(missing)
                + ". Treat this output as partial or malformed.\n"
            )
        chunks_meta.append(
            chunk_result(
                "chunk-001-of-001",
                call,
                missing,
                chunk_warnings,
                structured_result,
                structured_errors,
                not args.structured_result,
            )
        )
    except subprocess.TimeoutExpired as exc:
        output = f"DeepSeek delegation timed out after {args.timeout_seconds} seconds.\n"
        if exc.stdout:
            output += f"\nPartial stdout:\n{exc.stdout}"
        if exc.stderr:
            output += f"\nPartial stderr:\n{exc.stderr}"
        write_error_output(args, output, cwd, cwd_valid)
        envelope = make_result_envelope(
            args,
            cwd,
            cwd_valid,
            "timeout",
            selected_driver,
            124,
            chunks_meta,
            warnings + [output.strip()],
            started_at,
        )
        if args.json_result:
            emit_result(args, output, envelope)
        else:
            print(output, file=sys.stderr)
        return 124
    except DelegateTimeoutError as exc:
        output = f"DeepSeek delegation timed out after {args.timeout_seconds} seconds.\n"
        write_error_output(args, output, cwd, cwd_valid)
        envelope = make_result_envelope(
            args,
            cwd,
            cwd_valid,
            "timeout",
            selected_driver,
            124,
            chunks_meta,
            warnings + [str(exc)],
            started_at,
        )
        if args.json_result:
            emit_result(args, output, envelope)
        else:
            print(output, file=sys.stderr)
        return 124
    except DelegateExecutableError as exc:
        output = f"DeepSeek delegation setup failed: {exc}\n"
        write_error_output(args, output, cwd, cwd_valid)
        envelope = make_result_envelope(
            args,
            cwd,
            cwd_valid,
            "setup_error",
            selected_driver,
            127,
            chunks_meta,
            warnings + [str(exc)],
            started_at,
        )
        if args.json_result:
            emit_result(args, output, envelope)
        else:
            print(output, file=sys.stderr)
        return 127
    except DelegateSetupError as exc:
        output = f"DeepSeek delegation setup failed: {exc}\n"
        write_error_output(args, output, cwd, cwd_valid)
        envelope = make_result_envelope(
            args,
            cwd,
            cwd_valid,
            "setup_error",
            selected_driver,
            int(getattr(exc, "exit_code", 2)),
            chunks_meta,
            warnings + [str(exc)],
            started_at,
        )
        if args.json_result:
            emit_result(args, output, envelope)
        else:
            print(output, file=sys.stderr)
        return int(getattr(exc, "exit_code", 2))
    except Exception as exc:
        output = f"DeepSeek delegation failed before invocation: {exc}\n"
        write_error_output(args, output, cwd, cwd_valid)
        envelope = make_result_envelope(
            args,
            cwd,
            cwd_valid,
            "setup_error",
            selected_driver,
            1,
            chunks_meta,
            warnings + [str(exc)],
            started_at,
        )
        if args.json_result:
            emit_result(args, output, envelope)
        else:
            print(output, file=sys.stderr)
        return 1

    write_output(args.out, output, cwd if "cwd" in locals() else None)
    envelope = make_result_envelope(
        args,
        cwd,
        cwd_valid,
        final_status(returncode, chunks_meta),
        selected_driver,
        returncode,
        chunks_meta,
        warnings,
        started_at,
    )
    emit_result(args, output, envelope)

    return returncode


if __name__ == "__main__":
    raise SystemExit(main())

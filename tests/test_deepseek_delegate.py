import argparse
import io
import importlib.util
import json
import pathlib
import tempfile
import unittest
from unittest import mock

import yaml


ROOT = pathlib.Path(__file__).resolve().parents[1]
SKILL_PATH = ROOT / "_skill_package" / "deepseek-delegate" / "SKILL.md"
REFERENCE_DIR = ROOT / "_skill_package" / "deepseek-delegate" / "references"
SCRIPT_PATH = (
    ROOT
    / "_skill_package"
    / "deepseek-delegate"
    / "scripts"
    / "deepseek_delegate.py"
)
MCP_SCRIPT_PATH = (
    ROOT
    / "_skill_package"
    / "deepseek-delegate"
    / "scripts"
    / "deepseek_delegate_mcp.py"
)


def load_module():
    spec = importlib.util.spec_from_file_location("deepseek_delegate", SCRIPT_PATH)
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(module)
    return module


def load_mcp_module():
    spec = importlib.util.spec_from_file_location("deepseek_delegate_mcp", MCP_SCRIPT_PATH)
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(module)
    return module


class DeepSeekDelegateTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.delegate = load_module()
        cls.delegate_mcp = load_mcp_module()

    def args(self):
        return argparse.Namespace(
            input_json=None,
            input_transport="cli",
            task="Review the packet.",
            mode="audit",
            packet_profile="default",
            model="deepseek-v4-pro",
            provider="deepseek",
            driver="auto",
            backend_transport="auto",
            context_text=None,
            context_file=[],
            chunk_chars=0,
            chunk_boundary_regex=None,
            max_context_chars=24000,
            prompt_char_limit=24000,
            timeout_seconds=180,
            mcp_probe_timeout_seconds=8,
            max_findings_per_chunk=5,
            structured_result=False,
            sandbox_mode="read-only",
            approval_policy="never",
            out=None,
            json_result=False,
            _input_json_fields=set(),
            _resolved_backend_transport=None,
            _single_packet_attempted=False,
            _chunk_reason=None,
        )

    def test_skill_frontmatter_is_parseable_and_trigger_is_narrow(self):
        text = SKILL_PATH.read_text(encoding="utf-8")
        frontmatter = text.split("---", 2)[1]
        metadata = yaml.safe_load(frontmatter)

        self.assertEqual(metadata["name"], "deepseek-delegate")
        description = metadata["description"]
        self.assertIn("Pro-only packet-local advisory review", description)
        self.assertIn("deepseek-v4-pro", description)
        self.assertIn("bounded snippets, diffs, logs", description)
        self.assertIn("Do not use for implementation", description)
        self.assertIn("full-repo review", description)
        self.assertIn("architecture", description)
        self.assertIn("secrets", description)
        self.assertIn("cheap-model routing", description)
        self.assertLessEqual(len(description.split()), 120)

    def test_skill_body_keeps_weibo_detail_out_of_main_instructions(self):
        text = SKILL_PATH.read_text(encoding="utf-8")

        self.assertNotIn("source_tail", text)
        self.assertNotIn("immutable_blocks", text)
        self.assertNotIn("QUALITY_GATE", text)

    def test_reference_router_lists_expected_references_without_self_loop(self):
        text = (REFERENCE_DIR / "index.md").read_text(encoding="utf-8")

        for name in [
            "result-contract.md",
            "packet-types.md",
            "codex-side-routing.md",
            "agent-cli-delegation.md",
            "transport-patterns.md",
            "chinese-prose.md",
            "weibo-batch.md",
            "weibo-ablation-index.md",
        ]:
            self.assertIn(name, text)
        self.assertNotIn("- `index.md`", text)

    def test_profiles_are_pro_only_by_default(self):
        for profile, defaults in self.delegate.PROFILE_DEFAULTS.items():
            self.assertNotEqual(
                defaults.get("model"),
                "deepseek-v4-flash",
                f"{profile} should not default to Flash",
            )
            if "model" in defaults:
                self.assertEqual(defaults["model"], "deepseek-v4-pro")

    def test_explicit_model_override_is_still_compatible(self):
        args = self.args()
        args.packet_profile = "weibo-ablation"
        args.model = "custom-compatible-model"

        with mock.patch.object(
            self.delegate.sys,
            "argv",
            [
                "deepseek_delegate.py",
                "--packet-profile",
                "weibo-ablation",
                "--model",
                "custom-compatible-model",
            ],
        ):
            self.delegate.apply_profile_defaults(args)

        self.assertEqual(args.model, "custom-compatible-model")

    def test_no_runtime_model_router_arguments_exist(self):
        text = SCRIPT_PATH.read_text(encoding="utf-8")

        self.assertNotIn("--model-policy", text)
        self.assertNotIn("--route-preview", text)
        self.assertNotIn("cost_hint", text)
        self.assertNotIn("selected_model", text)

    def test_input_json_file_populates_request_fields(self):
        payload = {
            "task": "Review JSON packet.",
            "mode": "review",
            "packet_profile": "long-review",
            "context_text": "hello",
            "context_files": ["packet.md"],
            "options": {
                "json_result": True,
                "structured_result": True,
                "max_context_chars": 1234,
            },
        }
        with tempfile.TemporaryDirectory() as tmp:
            path = pathlib.Path(tmp) / "packet.deepseek.json"
            path.write_text(json.dumps(payload), encoding="utf-8")
            with mock.patch.object(
                self.delegate.sys,
                "argv",
                ["deepseek_delegate.py", "--input-json", str(path)],
            ):
                args = self.delegate.parse_args()

        self.assertEqual(args.input_transport, "json-file")
        self.assertEqual(args.task, "Review JSON packet.")
        self.assertEqual(args.mode, "review")
        self.assertEqual(args.packet_profile, "long-review")
        self.assertEqual(args.context_text, "hello")
        self.assertEqual(args.context_file, ["packet.md"])
        self.assertTrue(args.json_result)
        self.assertTrue(args.structured_result)
        self.assertEqual(args.max_context_chars, 1234)

    def test_input_json_stdin_populates_request_fields(self):
        payload = {"task": "Review stdin packet.", "context_text": "stdin text"}
        with mock.patch.object(
            self.delegate.sys,
            "argv",
            ["deepseek_delegate.py", "--input-json", "-"],
        ):
            with mock.patch.object(self.delegate.sys, "stdin", io.StringIO(json.dumps(payload))):
                args = self.delegate.parse_args()

        self.assertEqual(args.input_transport, "json-stdin")
        self.assertEqual(args.task, "Review stdin packet.")
        self.assertEqual(args.context_text, "stdin text")

    def test_input_json_rejects_invalid_json_and_missing_task(self):
        with mock.patch.object(
            self.delegate.sys,
            "argv",
            ["deepseek_delegate.py", "--input-json", "-"],
        ):
            with mock.patch.object(self.delegate.sys, "stdin", io.StringIO("{bad")):
                with self.assertRaises(self.delegate.DelegateArgumentError):
                    self.delegate.parse_args()

        with mock.patch.object(
            self.delegate.sys,
            "argv",
            ["deepseek_delegate.py", "--input-json", "-"],
        ):
            with mock.patch.object(self.delegate.sys, "stdin", io.StringIO('{"context_text":"x"}')):
                with self.assertRaises(self.delegate.DelegateArgumentError):
                    self.delegate.parse_args()

    def test_main_returns_json_envelope_for_input_json_parse_errors(self):
        with mock.patch.object(
            self.delegate.sys,
            "argv",
            ["deepseek_delegate.py", "--input-json", "-", "--json-result"],
        ):
            with mock.patch.object(self.delegate.sys, "stdin", io.StringIO("{bad")):
                stdout = io.StringIO()
                with mock.patch.object(self.delegate.sys, "stdout", stdout):
                    code = self.delegate.main()

        envelope = json.loads(stdout.getvalue())
        self.assertEqual(code, 2)
        self.assertEqual(envelope["result"]["status"], "setup_error")
        self.assertIn("--input-json is not valid JSON", envelope["result"]["warnings"][0])

    def test_assemble_context_rejects_sensitive_context_text(self):
        args = self.args()
        args.context_text = "API_TOKEN=abcdefghijklmnopqrstuvwxyz"

        with self.assertRaises(self.delegate.DelegateSetupError):
            self.delegate.assemble_context(args, None)

    def test_reserved_exec_file_and_stdin_invocations_do_not_put_prompt_in_argv(self):
        args = self.args()
        prompt = "FULL PROMPT SHOULD NOT BE IN ARGV"

        file_invocation = self.delegate.deepseek_invocation(
            args,
            prompt,
            "exec-file",
            pathlib.Path("packet.prompt.txt"),
        )
        stdin_invocation = self.delegate.deepseek_invocation(args, prompt, "exec-stdin")

        self.assertNotIn(prompt, file_invocation)
        self.assertNotIn(prompt, stdin_invocation)
        self.assertIn("--prompt-file", " ".join(file_invocation))
        self.assertIn("--stdin", " ".join(stdin_invocation))

    def test_resolve_backend_transport_rejects_unadvertised_file_transport(self):
        args = self.args()
        args.backend_transport = "exec-file"

        with mock.patch.object(self.delegate, "deepseek_exec_supports_transport", return_value=False):
            with self.assertRaisesRegex(self.delegate.DelegateSetupError, "reserved"):
                self.delegate.resolve_backend_transport(args, "exec")

    def test_deepseek_mcp_invocation_reuses_windows_shim_wrapper(self):
        with mock.patch.object(self.delegate, "deepseek_executable", return_value="C:/bin/deepseek.ps1"):
            with mock.patch.object(self.delegate.os, "name", "nt"):
                invocation = self.delegate.deepseek_mcp_invocation()

        self.assertEqual(invocation[:5], ["powershell.exe", "-NoProfile", "-ExecutionPolicy", "Bypass", "-File"])
        self.assertEqual(invocation[-1], "mcp-server")

    def test_transport_probe_reuses_windows_shim_wrapper(self):
        completed = mock.Mock(stdout="Usage: deepseek exec --prompt-file", stderr="")
        with mock.patch.object(self.delegate, "deepseek_executable", return_value="C:/bin/deepseek.ps1"):
            with mock.patch.object(self.delegate.os, "name", "nt"):
                with mock.patch.object(self.delegate.subprocess, "run", return_value=completed) as run:
                    self.assertTrue(self.delegate.deepseek_exec_supports_transport("exec-file"))

        invocation = run.call_args.args[0]
        self.assertEqual(invocation[:5], ["powershell.exe", "-NoProfile", "-ExecutionPolicy", "Bypass", "-File"])
        self.assertEqual(invocation[-2:], ["exec", "--help"])

    def test_mcp_arguments_use_prompt_field_when_available(self):
        tool = {"inputSchema": {"properties": {"prompt": {}, "task": {}}}}

        result = self.delegate.mcp_tool_arguments(
            tool, self.args(), "FULL PROMPT", "F:/Workspaces/deepseek-tui"
        )

        self.assertEqual(result["prompt"], "FULL PROMPT")
        self.assertEqual(result["task"], "Review the packet.")

    def test_mcp_arguments_use_instructions_field_when_prompt_is_absent(self):
        tool = {"inputSchema": {"properties": {"instructions": {}, "mode": {}}}}

        result = self.delegate.mcp_tool_arguments(
            tool, self.args(), "FULL PROMPT", None
        )

        self.assertEqual(result["instructions"], "FULL PROMPT")
        self.assertEqual(result["mode"], "audit")
        self.assertNotIn("prompt", result)

    def test_mcp_arguments_use_task_as_full_prompt_when_it_is_the_only_delegate_field(self):
        tool = {"inputSchema": {"properties": {"task": {}, "model": {}}}}

        result = self.delegate.mcp_tool_arguments(
            tool, self.args(), "FULL PROMPT", None
        )

        self.assertEqual(result["task"], "FULL PROMPT")
        self.assertEqual(result["model"], "deepseek-v4-pro")

    def test_mcp_arguments_forward_behavior_options_when_supported(self):
        tool = {
            "inputSchema": {
                "properties": {
                    "prompt": {},
                    "structured_result": {},
                    "timeout_seconds": {},
                    "max_context_chars": {},
                    "chunk_chars": {},
                    "max_findings_per_chunk": {},
                }
            }
        }
        args = self.args()
        args.structured_result = True
        args.timeout_seconds = 222
        args.max_context_chars = 333
        args.chunk_chars = 44
        args.max_findings_per_chunk = 6

        result = self.delegate.mcp_tool_arguments(tool, args, "FULL PROMPT", None)

        self.assertTrue(result["structured_result"])
        self.assertEqual(result["timeout_seconds"], 222)
        self.assertEqual(result["max_context_chars"], 333)
        self.assertEqual(result["chunk_chars"], 44)
        self.assertEqual(result["max_findings_per_chunk"], 6)

    def test_mcp_envelope_status_controls_exit_code_and_structured_output(self):
        args = self.args()
        args.structured_result = True
        envelope = {
            "result": {
                "status": "ok",
                "chunks": [
                    {
                        "structured_ok": True,
                        "structured_result": {
                            "answer": "ok",
                            "findings": [],
                            "uncertainty": [],
                            "suggested_codex_checks": [],
                        },
                    }
                ],
            }
        }

        code, output = self.delegate.normalize_mcp_delegate_output(
            args,
            json.dumps(envelope),
        )

        self.assertEqual(code, 0)
        self.assertEqual(json.loads(output)["answer"], "ok")

    def test_mcp_envelope_setup_error_maps_to_nonzero_exit_code(self):
        code, output = self.delegate.normalize_mcp_delegate_output(
            self.args(),
            json.dumps({"result": {"status": "setup_error", "warnings": ["bad"]}}),
        )

        self.assertEqual(code, 2)
        self.assertIn("setup_error", output)

    def test_missing_required_headings_ignores_fenced_code(self):
        output = "\n".join(
            [
                "```",
                "## Answer",
                "```",
                "## Answer",
                "## Evidence",
                "## Uncertainty",
                "## Suggested Codex Checks",
            ]
        )

        self.assertEqual(self.delegate.missing_required_headings(output), [])

    def test_structured_result_parses_valid_fenced_json(self):
        output = """```json
{"answer":"ok","findings":[{"severity":"low","claim":"c","evidence":"e","codex_check":"check"}],"uncertainty":[],"suggested_codex_checks":["run tests"]}
```"""

        result, errors = self.delegate.parse_structured_result(output)

        self.assertEqual(errors, [])
        self.assertEqual(result["answer"], "ok")
        self.assertEqual(result["findings"][0]["severity"], "low")

    def test_structured_result_accepts_empty_findings(self):
        output = """{"answer":"no concrete findings","findings":[],"uncertainty":[],"suggested_codex_checks":[]}"""

        result, errors = self.delegate.parse_structured_result(output)

        self.assertEqual(errors, [])
        self.assertEqual(result["findings"], [])

    def test_structured_result_reports_missing_fields(self):
        output = """{"answer":"bad","findings":[]}"""

        _result, errors = self.delegate.parse_structured_result(output)

        self.assertIn("missing root field: uncertainty", errors)
        self.assertIn("missing root field: suggested_codex_checks", errors)

    def test_structured_result_rejects_invalid_severity_and_non_string_lists(self):
        output = """{"answer":"bad","findings":[{"severity":"critical","claim":"c","evidence":"e","codex_check":"check"}],"uncertainty":[123],"suggested_codex_checks":[{}]}"""

        _result, errors = self.delegate.parse_structured_result(output)

        self.assertIn("finding 1 severity must be one of: low, medium, high", errors)
        self.assertIn("uncertainty 1 must be a string", errors)
        self.assertIn("suggested_codex_checks 1 must be a string", errors)

    def test_structured_result_reports_bad_json(self):
        output = """```json
{"answer": "bad",}
```"""

        _result, errors = self.delegate.parse_structured_result(output)

        self.assertTrue(errors)
        self.assertIn("invalid JSON", errors[0])

    def test_chunk_results_mark_structured_errors_partial(self):
        call = {
            "driver": "exec",
            "exit_code": 0,
            "duration_seconds": 0.1,
            "output": "{}",
        }

        good = self.delegate.chunk_result(
            "chunk-001-of-002",
            call,
            [],
            [],
            {
                "answer": "ok",
                "findings": [],
                "uncertainty": [],
                "suggested_codex_checks": [],
            },
            [],
            True,
        )
        bad = self.delegate.chunk_result(
            "chunk-002-of-002",
            call,
            [],
            [],
            {"answer": "bad"},
            ["missing root field: findings"],
            False,
        )

        self.assertEqual(good["status"], "ok")
        self.assertTrue(good["headings_checked"])
        self.assertEqual(bad["status"], "partial")
        self.assertFalse(bad["headings_checked"])
        self.assertEqual(self.delegate.final_status(0, [good, bad]), "partial")

    def test_boundary_chunking_keeps_blocks_intact(self):
        text = "Candidate 1:\nalpha\nCandidate 2:\nbeta\nCandidate 3:\ngamma\n"

        chunks = self.delegate.split_text(
            text,
            chunk_chars=32,
            boundary_regex=r"^\s*Candidate\s+\d+:",
        )

        self.assertEqual(len(chunks), 3)
        self.assertTrue(all(chunk.startswith("Candidate") for chunk in chunks))

    def test_sensitive_text_rejects_secret_like_context(self):
        with self.assertRaises(self.delegate.DelegateSetupError):
            self.delegate.reject_sensitive_text(
                "API_TOKEN=abcdefghijklmnopqrstuvwxyz", "unit test"
            )

    def test_mcp_driver_fails_closed_when_no_delegate_tool_exists(self):
        args = self.args()
        args.driver = "mcp"

        with mock.patch.object(self.delegate, "list_mcp_tools", return_value=[]):
            with self.assertRaisesRegex(RuntimeError, "no delegate/review MCP tool"):
                self.delegate.resolve_driver(args, None)

    def test_mcp_probe_uses_short_probe_timeout_not_delegate_timeout(self):
        args = self.args()
        args.driver = "auto"
        args.timeout_seconds = 360
        args.mcp_probe_timeout_seconds = 5

        with mock.patch.object(self.delegate, "list_mcp_tools", return_value=[]) as probe:
            self.delegate.resolve_driver(args, None)

        probe.assert_called_once_with(None, 5)

    def test_windows_command_limit_keeps_cmd_conservative(self):
        self.assertEqual(self.delegate.windows_command_limit(["cmd.exe"]), 7800)

    def test_local_mcp_wrapper_exposes_only_delegate_review_tool(self):
        result = self.delegate_mcp.handle_request(
            {"jsonrpc": "2.0", "id": 1, "method": "tools/list"}
        )

        tools = result["result"]["tools"]
        self.assertEqual([tool["name"] for tool in tools], ["deepseek_delegate_review"])
        description = tools[0]["description"].lower()
        self.assertIn("bounded", description)
        self.assertNotIn("shell", tools[0]["name"])
        self.assertNotIn("command", tools[0]["name"])

    def test_local_mcp_wrapper_calls_delegate_runner_with_json_arguments(self):
        def fake_runner(arguments):
            return {"result": {"status": "ok", "task": arguments["task"]}}

        result = self.delegate_mcp.handle_request(
            {
                "jsonrpc": "2.0",
                "id": 2,
                "method": "tools/call",
                "params": {
                    "name": "deepseek_delegate_review",
                    "arguments": {"task": "Review packet.", "context_text": "hello"},
                },
            },
            fake_runner,
        )

        text = result["result"]["content"][0]["text"]
        self.assertEqual(json.loads(text)["result"]["status"], "ok")

    def test_local_mcp_wrapper_unknown_tool_fails_closed(self):
        result = self.delegate_mcp.handle_request(
            {
                "jsonrpc": "2.0",
                "id": 3,
                "method": "tools/call",
                "params": {"name": "exec_shell", "arguments": {}},
            }
        )

        self.assertEqual(result["error"]["code"], -32601)

    def test_local_mcp_wrapper_returns_envelope_for_helper_timeout(self):
        with mock.patch.object(
            self.delegate_mcp.subprocess,
            "run",
            side_effect=self.delegate_mcp.subprocess.TimeoutExpired(["python"], 60),
        ):
            result = self.delegate_mcp.run_delegate_review({"task": "Review packet."})

        self.assertEqual(result["result"]["status"], "timeout")
        self.assertEqual(result["result"]["exit_code"], 124)

    def test_local_mcp_wrapper_returns_envelope_for_bad_arguments(self):
        result = self.delegate_mcp.run_delegate_review({"context_text": "missing task"})

        self.assertEqual(result["result"]["status"], "setup_error")
        self.assertEqual(result["result"]["exit_code"], 2)


if __name__ == "__main__":
    unittest.main()

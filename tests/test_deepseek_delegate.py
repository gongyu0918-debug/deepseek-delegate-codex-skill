import argparse
import importlib.util
import pathlib
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


def load_module():
    spec = importlib.util.spec_from_file_location("deepseek_delegate", SCRIPT_PATH)
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(module)
    return module


class DeepSeekDelegateTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.delegate = load_module()

    def args(self):
        return argparse.Namespace(
            task="Review the packet.",
            mode="audit",
            packet_profile="default",
            model="deepseek-v4-pro",
            provider="deepseek",
            driver="auto",
            context_file=[],
            chunk_chars=0,
            chunk_boundary_regex=None,
            max_context_chars=24000,
            prompt_char_limit=24000,
            timeout_seconds=180,
            max_findings_per_chunk=5,
            structured_result=False,
            sandbox_mode="read-only",
            approval_policy="never",
            out=None,
            json_result=False,
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

    def test_windows_command_limit_keeps_cmd_conservative(self):
        self.assertEqual(self.delegate.windows_command_limit(["cmd.exe"]), 7800)


if __name__ == "__main__":
    unittest.main()

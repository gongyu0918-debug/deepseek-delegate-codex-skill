# Privacy Boundary

Load this file before approving any new Codex Review Helper use case, host integration, or repeated workflow.

## Non-Training Contract

This skill is a local helper adapter for one-off advisory review through the user's configured external review CLI. It is not a training pipeline, data collection pipeline, model evaluation harness, benchmark runner, or corpus labeling workflow.

This boundary is aligned with OpenAI's published Terms of Use: do not automatically or programmatically extract OpenAI/Codex output, and do not use OpenAI output to develop competing models. See https://openai.com/policies/terms-of-use/.

The external review CLI may receive only:

- the explicit `task` string;
- optional `context_text`;
- contents of explicitly listed `context_files`;
- helper framing needed to request structured findings.

The external review CLI must not receive:

- hidden Codex or GPT system/developer prompts;
- full conversation history;
- Codex memory, workspace indexes, or files not explicitly attached;
- environment variables, cookies, credential files, API keys, tokens, or login state;
- batches of generated prompts, model outputs, scoring examples, training/evaluation datasets, or social workflow calibration samples.

## Forbidden Uses

- Batch, queue, or map/reduce delegation.
- A/B prompt ablation, repeated calibration, benchmark labeling, or scoring pipelines.
- Any workflow that transfers many Codex/GPT-produced packets to another model.
- Any workflow that sends helper output back to the external CLI for iterative grading, correction, labeling, or calibration.
- Any task where the packet would be valuable as a third-party dataset.
- Any task where the user has not accepted that the explicit packet will be sent to their configured external CLI.

## Safe Shape

Use one bounded packet, one review request, and one structured result. If the packet is too large for the active transport, shrink it or keep the work in Codex. Do not split it into repeated delegate calls.

Codex remains responsible for final judgment, local verification, file changes, and user-facing conclusions.

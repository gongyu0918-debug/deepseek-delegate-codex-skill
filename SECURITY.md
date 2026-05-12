# Security

## Data Boundary

Codex Review Helper is a disclosure reducer, not a privacy guarantee. It blocks obvious secrets and restricts the helper to one explicit review packet, but any packet sent to a remote model provider may still be processed under that provider's terms.

Do not use the helper for private credentials, customer data, unpublished business material, full repositories, generated corpora, model evaluation datasets, or batch workflows.

## Provider Review

The npm wrapper for `deepseek-tui` launches downloaded release binaries. Review the installed package and binary provenance before use:

```powershell
where.exe deepseek
deepseek --version
deepseek doctor
```

The helper does not hide or bypass provider policy. If the configured provider cannot be trusted for a packet, do not send that packet.

The helper invokes the configured CLI with telemetry disabled for that process, read-only sandbox mode, no approvals, and an isolated working directory. These controls reduce accidental disclosure, but they do not change the remote provider's data handling.

Optional global hardening for the external CLI:

```powershell
deepseek config set allow_shell false
deepseek config set approval_policy never
deepseek config set sandbox_mode read-only
```

## Reporting

Open an issue with a minimal, non-secret reproduction. Do not include API keys, cookies, config files, private logs, or proprietary source.

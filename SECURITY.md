# Security Policy

Persistent Memory MCP is a local-first memory server that can store project context, repository metadata and user-provided information. Security reports are handled privately so fixes can be prepared before public disclosure.

## Supported versions

Security fixes target the current `0.3.x` line and the latest supported source state on `main`. Older releases may not receive patches unless the issue materially affects a supported upgrade path.

## Reporting a vulnerability

**Do not open a public GitHub issue for a suspected vulnerability.**

Use GitHub's private vulnerability reporting for this repository when that option is available. If private reporting is unavailable, contact **hola@dannymaaz.com** and include only the information needed to reproduce and assess the problem:

- affected version/commit and operating system;
- minimal reproducible steps or proof of concept;
- expected and observed behavior;
- likely security impact and affected boundary;
- suggested mitigation, if known.

Do not send real credentials, production secrets, unrelated personal data or destructive payloads. Redact sensitive values and use synthetic fixtures where possible.

## In scope

Examples include:

- secret/credential leakage or redaction bypasses;
- owner/project isolation failures;
- unsafe file, path, subprocess or command handling;
- unintended remote exposure of localhost-only Dashboard/Galaxy surfaces;
- bypasses of signed destructive-operation confirmations;
- backup, restore or migration behavior that can cause unintended data loss;
- dependency vulnerabilities that affect supported configurations;
- malicious or malformed MCP inputs that cross documented trust boundaries.

## Out of scope

General support questions, feature requests, performance tuning and product-scope proposals should use normal GitHub Issues when appropriate. Reports that require access to third-party accounts or data without authorization are not accepted.

## Disclosure and remediation

Reports will be triaged against the current local-first threat model. Valid vulnerabilities should be fixed and regression-tested before coordinated public disclosure. A fix may include code changes, documentation changes, dependency updates or a release advisory depending on impact.

The project does not promise that optional self-managed remote adapters provide a hosted multi-tenant security model; team workspaces, public collaborative dashboards and managed SaaS isolation are outside the product scope.

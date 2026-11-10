# Project Handover 0.1.0-rc3

Third release candidate for the standalone local SQLite edition. The complete [English guide](README.md) and [German guide](README.de.md) cover installation, a hands-on Quick Start, the shared workflow, troubleshooting, maintenance and security boundaries. The CLI, database schema and tests are identical to `0.1.0-rc2`.

- Record reports, attach an immutable review proposal, and require an explicit decision before a worker can claim a task.
- Track state changes in SQLite. Repeating the same operation is safe, and completion records the next report in the same transaction.
- Inspect status without exposing report bodies in list or event output. Pause the ledger with its mode switch.

Use it from a terminal or from trusted agent sessions with access to the same database file on the same host. This edition has no Google Sheets bridge, automatic cloud synchronization, built-in scheduler or agent orchestration. A human operator is expected to enter decisions. Approval records enforce workflow state and do not authenticate the approver. Access control relies on filesystem permissions.

Verification covers the 14 automated CLI tests on Linux, both README walkthroughs, the Agent Skills format, and Codex discovery and removal in an isolated project. Live model invocation and platform schedulers remain unverified.

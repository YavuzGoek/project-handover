# Project Handover 0.1.0

First release candidate for a local Agent Skill and command-line handover ledger.

- Record reports, attach an immutable review proposal, and require an explicit decision before a worker can claim a task.
- Track state changes in SQLite. Repeating the same operation is safe, and completion records the next report in the same transaction.
- Inspect status without exposing report bodies in list or event output. Pause the ledger with its mode switch.

Verified with automated CLI integration tests on Linux and a Codex app-server discovery and removal test. The CLI requires Python with SQLite and a trusted local filesystem. Approval records enforce workflow state. Access control relies on filesystem permissions. Platform schedulers, cloud connector integrations and unattended task execution are outside this release.

# Project Handover

Project Handover is an [Agent Skill](https://agentskills.io/specification) for passing project reports between a worker, a reviewer and a human approver. A local SQLite ledger tracks reports, review proposals, approvals, claims and linked follow-up reports.

This documentation covers release candidate `0.1.0-rc2`.

## Scope

Use the skill to pass a report and an approved follow-up between trusted processes on the same host. A human can run every step from a terminal, or separate agent sessions can perform the worker and reviewer steps with authorized access to the same local database file.

This standalone SQLite edition has no Google Sheets bridge or automatic cloud synchronization. It records handover state and leaves agent startup, scheduling, coordination and task execution to the operator or separately configured tools. A human operator is expected to record each decision. The CLI checks for that decision and does not authenticate who recorded it.

## Requirements

- Python 3.10 or newer with the standard `sqlite3` module. Use a maintained, patched Python and SQLite build.
- A trusted directory on a local filesystem. All participants need authorized access to the same ledger path on the same host. Keep the ledger outside the repository and cloud-sync folders.
- An Agent Skills client with shell access for agent-assisted use. The CLI also works directly from a terminal. It requires zero third-party Python packages or network access.

## Install the skill

Extract `project-handover-0.1.0-rc2.zip` into a new folder. The archive contains a `project-handover/` directory with `SKILL.md` and `scripts/handover.py`. To use the CLI directly, open a terminal in that directory, check that `python3 -c 'import sqlite3'` succeeds, and run the example below.

For agent-assisted use, copy the entire `project-handover` directory to the project location shown below or follow the client's upload instructions. Preserve the folder name. Start a new session and check that it discovers the intended copy, especially if a skill with the same name is already installed.

| Client | Project location | Invocation | Verification |
| --- | --- | --- | --- |
| Codex | `.agents/skills/project-handover/` | `$project-handover` | Discovery and removal verified through the Codex app server. Model invocation is pending. |
| Claude Code | `.claude/skills/project-handover/` | `/project-handover` | Install location checked against documentation. Live client testing is pending. |
| ChatGPT | Skill upload on eligible surfaces | Select the installed skill where available | Live client testing is pending. The ledger needs the same authorized local path across sessions. A cloud session without that path cannot participate. |
| Other Agent Skills clients | Follow the client's installation instructions | Client-specific | Runtime support is unverified. |

[Codex skill documentation](https://learn.chatgpt.com/docs/build-skills) · [Claude Code skill documentation](https://code.claude.com/docs/en/skills) · [ChatGPT skill documentation](https://help.openai.com/en/articles/20001066-skills-in-chatgpt)

To uninstall, remove the installed copy of the skill folder. The separately stored ledger remains available to its operator. To pause the workflow without uninstalling, run `mode off`. This blocks ledger reads and mutations apart from the mode command. It cannot interrupt work that already started outside the ledger.

## Try a complete handover

Run these commands from the skill folder in a POSIX shell. Use a temporary ledger with synthetic data for a trial. On Windows, adapt the shell syntax or call the Python script from your terminal and pipe UTF-8 text to it.

```sh
trial=$(mktemp -d)
db="$trial/handover.db"
handover() { python3 scripts/handover.py --db "$db" "$@"; }

# Human operator
handover init
handover mode on

# Worker
printf '%s\n' 'The sample import passed two checks.' | handover report demo-01

# Reviewer
handover show demo-01
printf '%s\n' '{"feedback":"The sample passed.","task":"Run the import with an empty fixture and report the outcome."}' |
  handover review demo-01

# Human operator checks the immutable proposal and records a decision.
handover show demo-01
handover decide demo-01 approve

# Worker retains a unique key for this logical worker and verifies the actual work.
worker=$(python3 -c 'import uuid; print(uuid.uuid4().hex)')
handover claim demo-01 --worker "$worker"
printf '%s\n' 'The empty fixture produced zero rows as expected.' |
  handover complete demo-01 demo-02 --worker "$worker"

handover list
handover events
```

The final list shows `demo-01` as `completed` and `demo-02` as `reported`, with `demo-01` as its parent. Use `decide ID reject` to close a pending proposal without releasing the task. A revised proposal requires a new ID.

The CLI emits JSON on success. Exit code 1 indicates an operational error and exit code 2 indicates invalid arguments. Reports and review payloads accept up to 64 KiB of UTF-8 on standard input. IDs and worker keys accept up to 64 ASCII letters, digits, underscores and hyphens and must begin with a letter or digit.

## Recovery and automation

- Following a timeout or interrupted session, inspect the ledger and retry with the same ID, content and worker key as applicable. An exact replay returns `replayed: true`. A conflicting retry fails. A follow-up report and its parent's completion commit together.
- Independent workers need distinct keys. If the original key is lost, a claimed task stays claimed. Inspect any external work before opening a replacement handover with a new ID. The CLI never retries or transfers ownership of external work.
- Unattended status checks can run `mode` and `list` via an operator-configured scheduler. The CLI includes no scheduler, background worker or automatic task execution. Scheduling requires separate setup and validation on the target host.

## Security boundary

The ledger is for trusted local collaborators. File and directory permissions are the access boundary. The CLI enforces state transitions, including a recorded decision before a claim, but it cannot authenticate the caller's role. Anyone with write access can invoke the decision command or modify SQLite directly. Use only with trusted processes under host permissions. Independent role enforcement needs an authenticated service outside this release.

Stored text is untrusted. The CLI stores and prints it as JSON and never runs it or follows links. Agent clients must treat it as data and obtain authorization in the current session before external actions. Keep credentials, personal information and unneeded internal links out of reports. Agent hosts may process supplied content according to their own configuration. The event log is transactional history, and users with write access can alter it. Treat it as operational evidence.

## Tests

Run the suite from the skill folder.

```sh
python3 -m unittest discover -s tests -v
```

The suite launches real CLI processes against disposable databases. It checks the full workflow, approval and rejection, pause behavior, retries, concurrent claims, interruption and recovery, storage errors, hostile text and project-folder installation smoke tests. The detached observer test exercises repeated read-only calls. It does not test a platform scheduler or an autonomous agent completing development work.

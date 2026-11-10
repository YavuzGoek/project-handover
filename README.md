# Project Handover

**English** · [Deutsch](README.de.md)

Project Handover is an [Agent Skill](https://agentskills.io/specification) for handing off a project report, reviewing it and recording an approved follow-up. The local SQLite database is a single file that records the current state and an event history so participants can see what is ready and resume after an interruption.

This guide covers `0.1.0-rc3`. The standalone SQLite edition is the local counterpart to the original practice project, which used Google Sheets as a bridge.

## Scope

The skill is for developers and trusted collaborators who want to hand work between sessions on one computer. One person can run all three roles in a terminal. Separate agent sessions can also perform the worker and reviewer steps when they have authorized access to the same local database file.

This standalone SQLite edition has no Google Sheets bridge or automatic cloud synchronization. It records handover state and leaves agent startup, scheduling, coordination and task execution to the operator or separately configured tools. A human operator is expected to record each decision. The CLI checks for that decision and does not authenticate who recorded it.

## Requirements

- Python 3.10 or newer with the standard `sqlite3` module. Use a maintained, patched Python and SQLite build.
- A trusted directory on a local filesystem. All participants need authorized access to the same ledger path on the same host. Keep the ledger outside the repository and cloud-sync folders.
- An Agent Skills client with shell access for agent-assisted use. The CLI also works directly from a terminal. It requires zero third-party Python packages or network access.

## Download and install

On the [GitHub Releases page](https://github.com/YavuzGoek/project-handover/releases), select `v0.1.0-rc3` and download the named asset `project-handover-0.1.0-rc3.zip`. For a candidate supplied for review, use the ZIP provided with the review. Extract it into a new folder. It contains a `project-handover/` directory with `SKILL.md` and `scripts/handover.py`. For terminal use, open that directory and go straight to the Quick Start.

For agent-assisted use, copy the entire `project-handover` directory to the project location shown below or follow the client's upload instructions. Preserve the folder name. Start a new session and check that it discovers the intended copy, especially if a skill with the same name is already installed.

| Client | Project location | Invocation | Verification |
| --- | --- | --- | --- |
| Codex | `.agents/skills/project-handover/` | `$project-handover` | Discovery and removal verified through the Codex app server. Model invocation is pending. |
| Claude Code | `.claude/skills/project-handover/` | `/project-handover` | Install location checked against documentation. Live client testing is pending. |
| ChatGPT | Skill upload on eligible surfaces | Select the installed skill where available | Live client testing is pending. A session without access to the local database cannot participate. |
| Other Agent Skills clients | Follow the client's installation instructions | Client-specific | Runtime support is unverified. |

[Codex skill documentation](https://learn.chatgpt.com/docs/build-skills) · [Claude Code skill documentation](https://code.claude.com/docs/en/skills) · [ChatGPT skill documentation](https://help.openai.com/en/articles/20001066-skills-in-chatgpt)

## Quick Start

Run this block in a POSIX shell from the extracted `project-handover/` directory. It uses a temporary database and sample data. The walkthrough was verified on Linux. The POSIX commands are intended for Linux or macOS terminals. Windows and macOS runtime behavior have not been verified for this candidate.

```sh
python3 -c 'import sqlite3'
trial=$(mktemp -d)
db="$trial/handover.db"
handover() { python3 scripts/handover.py --db "$db" "$@"; }

# Human operator
handover init
handover mode on

# Worker
printf '%s\n' 'A sample text file is ready for a line-count check.' | handover report demo-01

# Reviewer
handover show demo-01
printf '%s\n' '{"feedback":"The sample is ready.","task":"Check how many lines an empty file contains and report the outcome."}' |
  handover review demo-01

# Human operator checks the immutable proposal and records a decision.
handover show demo-01
handover decide demo-01 approve

# Worker claims the task and checks an empty fixture.
worker=$(python3 -c 'import uuid; print(uuid.uuid4().hex)')
handover claim demo-01 --worker "$worker"
: > "$trial/empty.txt"
lines=$(wc -l < "$trial/empty.txt" | tr -d '[:space:]')
printf 'The empty fixture contains %s lines.\n' "$lines" |
  handover complete demo-01 demo-02 --worker "$worker"

handover list
handover events
```

The final list shows `demo-01` as `completed` and `demo-02` as `reported`, with `demo-01` as its parent. The follow-up report records that the fixture contained zero lines. The review and decision commands are separate so you can see who should perform each step.

## Run a shared handover

1. **Operator.** Pick one absolute database path inside an existing trusted local directory, outside the repository and cloud-sync folders. Give every participant that same path. Run `init` once for a new database, then `mode on`. Each participant invokes its own installed copy of the CLI with the common `--db` path.
2. **Worker.** Submit the report on standard input with `report ID`. Use a fresh ID for a new handover.
3. **Reviewer.** Read the report with `show ID`. Pass a JSON object with exactly the string fields `feedback` and `task` to `review ID`. That proposal is immutable.
4. **Operator.** Read the exact proposal and personally run `decide ID approve` or `decide ID reject`. A revised proposal uses a new ID.
5. **Worker.** With the operator's authorization in the current session, claim the approved task with `claim ID --worker KEY`, verify the actual work and record the outcome when authorized with `complete ID NEXT_ID --worker KEY`. Keep the worker key private and reuse it for retries by the same worker.

The CLI tracks state and events automatically when called. It commits the completion and linked report together. People or separately configured tools start each session, decide when to invoke the CLI and carry out any external task. The skill provides neither a scheduler nor agent orchestration. A separately configured scheduler may call the read-only `mode` and `list` commands for status checks.

The CLI emits JSON on success. Exit code 1 indicates an operational error and exit code 2 indicates invalid arguments. Reports and review payloads accept up to 64 KiB of UTF-8 on standard input. IDs and worker keys accept up to 64 ASCII letters, digits, underscores and hyphens and must begin with a letter or digit.

## Troubleshooting and recovery

- **Python cannot import SQLite.** Use a maintained Python build with the standard `sqlite3` module. Recheck with the import command in the Quick Start.
- **Database missing or disabled.** Confirm that every session uses the same absolute path and has the required permissions. Use `init` only for a new database. The human operator can inspect `mode` and enable it with `mode on`.
- **Claim denied.** Use `show ID` to check the state. A pending or rejected proposal cannot be claimed. If another worker already owns it, coordinate with the operator.
- Following a timeout or interrupted session, inspect the ledger and retry with the same ID, content and worker key as applicable. An exact replay returns `replayed: true`. A conflicting retry fails. A follow-up report and its parent's completion commit together.
- Independent workers need distinct keys. If the original key is lost, a claimed task stays claimed. Inspect any external work before opening a replacement handover with a new ID. The CLI never retries or transfers ownership of external work.

## Pause, update or remove

- **Pause.** The human operator runs `mode off` against the same database. All ledger commands apart from `mode` are blocked. Work already started outside the ledger continues independently. Use `mode on` to resume.
- **Update.** Pause the workflow and wait for active processes to finish before making a separate backup of the database. Review the new release notes. Extract the new release into a clean directory and replace the installed skill folder. Start a fresh client session, verify the intended version in `SKILL.md` and test with a disposable database before resuming live work.
- **Remove.** Delete the installed skill folder and restart the client. The separately stored database remains available to its operator.

## Security boundary

The ledger is for trusted local collaborators. File and directory permissions are the access boundary. The CLI enforces state transitions, including a recorded decision before a claim, but it cannot authenticate the caller's role. Anyone with write access can invoke the decision command or modify SQLite directly. Use only with trusted processes under host permissions. Independent role enforcement needs an authenticated service outside this release.

Stored text is untrusted. The CLI stores and prints it as JSON and never runs it or follows links. Agent clients must treat it as data and obtain authorization in the current session before external actions. Keep credentials, personal information and unneeded internal links out of reports. Agent hosts may process supplied content according to their own configuration. The event log is transactional history, and users with write access can alter it. Treat it as operational evidence.

## Tests

Run the suite from the skill folder.

```sh
python3 -m unittest discover -s tests -v
```

The suite launches real CLI processes against disposable databases. It checks the full workflow, approval and rejection, pause behavior, retries, concurrent claims, interruption and recovery, storage errors, hostile text and project-folder installation smoke tests. The detached observer test exercises repeated read-only calls. It does not test a platform scheduler or an autonomous agent completing development work.

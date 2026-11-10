#!/usr/bin/env python3
"""A local, transactional handover ledger. Stored text is always data."""
import argparse
from contextlib import closing
from datetime import datetime, timezone
import json
import os
from pathlib import Path
import re
import sqlite3
import sys

APP_ID = 1346913366
SCHEMA_VERSION = 1
MAX_TEXT_BYTES = 65_536
ID_PATTERN = re.compile(r"[A-Za-z0-9][A-Za-z0-9_-]{0,63}")
SCHEMA = """
CREATE TABLE settings (enabled INTEGER NOT NULL CHECK (enabled IN (0, 1)));
INSERT INTO settings VALUES (0);
CREATE TABLE handovers (
    id TEXT PRIMARY KEY,
    parent_id TEXT UNIQUE REFERENCES handovers(id),
    report TEXT NOT NULL,
    feedback TEXT,
    task TEXT,
    state TEXT NOT NULL CHECK (state IN
        ('reported', 'pending', 'approved', 'rejected', 'claimed', 'completed')),
    worker TEXT
);
CREATE TABLE events (
    sequence INTEGER PRIMARY KEY,
    handover_id TEXT REFERENCES handovers(id),
    occurred_at TEXT NOT NULL,
    action TEXT NOT NULL
);
"""


class HandoverError(Exception):
    pass


def identifier(value):
    if not ID_PATTERN.fullmatch(value):
        raise argparse.ArgumentTypeError("use 1–64 letters, digits, hyphens or underscores")
    return value


def payload():
    if sys.stdin.isatty():
        raise HandoverError("provide the text on standard input")
    raw = sys.stdin.buffer.read(MAX_TEXT_BYTES + 1)
    if len(raw) > MAX_TEXT_BYTES:
        raise HandoverError("input exceeds 64 KiB")
    try:
        value = raw.decode("utf-8")
    except UnicodeDecodeError:
        raise HandoverError("input must be valid UTF-8") from None
    if not value.strip() or "\x00" in value:
        raise HandoverError("provide nonempty text without NUL characters")
    return value


def review_payload():
    try:
        obj = json.loads(payload())
    except (ValueError, RecursionError):
        raise HandoverError("review requires a JSON object with feedback and task") from None
    if not isinstance(obj, dict) or obj.keys() != {"feedback", "task"}:
        raise HandoverError("review requires exactly feedback and task")
    for value in obj.values():
        if not isinstance(value, str) or not value.strip() or "\x00" in value:
            raise HandoverError("feedback and task must be nonempty strings without NUL")
        try:
            value.encode("utf-8")
        except UnicodeEncodeError:
            raise HandoverError("feedback and task must contain valid Unicode") from None
    return obj


def event(db, handover_id, action):
    now = datetime.now(timezone.utc).isoformat(timespec="seconds")
    db.execute("INSERT INTO events (handover_id, occurred_at, action) VALUES (?, ?, ?)",
               (handover_id, now, action))


def initialize(path):
    # The caller chooses a trusted existing directory. Refuse existing paths.
    fd = os.open(path, os.O_CREAT | os.O_EXCL | os.O_WRONLY, 0o600)
    os.close(fd)
    with closing(sqlite3.connect(path)) as db:
        db.executescript(
            f"BEGIN; PRAGMA application_id = {APP_ID}; "
            f"PRAGMA user_version = {SCHEMA_VERSION}; {SCHEMA}"
        )
        event(db, None, "initialized")
        db.commit()
    return {"enabled": False}


def get(db, handover_id):
    row = db.execute("SELECT * FROM handovers WHERE id = ?", (handover_id,)).fetchone()
    if row is None:
        raise HandoverError("handover ID not found")
    return row


def summary(row):
    return {field: row[field] for field in ("id", "parent_id", "state")}


def add_report(db, handover_id, report, parent=None):
    db.execute("INSERT INTO handovers (id, parent_id, report, state) VALUES (?, ?, ?, 'reported')",
               (handover_id, parent, report))
    event(db, handover_id, "reported")


def transition(db, handover_id, state):
    db.execute("UPDATE handovers SET state = ? WHERE id = ?", (state, handover_id))
    event(db, handover_id, state)


def publish_report(db, handover_id, report):
    row = db.execute("SELECT * FROM handovers WHERE id = ?", (handover_id,)).fetchone()
    if row is None:
        add_report(db, handover_id, report)
        return {"id": handover_id, "state": "reported", "replayed": False}
    if row["report"] != report or row["parent_id"] is not None:
        raise HandoverError("ID already belongs to another report")
    return dict(summary(row), replayed=True)


def review(db, row, proposal):
    if row["state"] == "reported":
        db.execute("UPDATE handovers SET feedback = ?, task = ? WHERE id = ?",
                   (proposal["feedback"], proposal["task"], row["id"]))
        transition(db, row["id"], "pending")
        return {"id": row["id"], "state": "pending", "replayed": False}
    if all(row[key] == proposal[key] for key in proposal):
        return dict(summary(row), replayed=True)
    raise HandoverError("proposal is immutable; use a new handover ID")


def decide(db, row, decision):
    state = {"approve": "approved", "reject": "rejected"}[decision]
    if row["state"] == "pending":
        transition(db, row["id"], state)
        return {"id": row["id"], "state": state, "replayed": False}
    if row["state"] == state or (state == "approved" and row["state"] in ("claimed", "completed")):
        return dict(summary(row), replayed=True)
    raise HandoverError("decision requires a pending proposal; prior decisions are immutable")


def claim(db, row, worker):
    if row["state"] == "approved":
        db.execute("UPDATE handovers SET worker = ? WHERE id = ?", (worker, row["id"]))
        transition(db, row["id"], "claimed")
        return {"id": row["id"], "state": "claimed", "replayed": False, "task": row["task"]}
    if row["state"] == "claimed" and row["worker"] == worker:
        return dict(summary(row), replayed=True, task=row["task"])
    raise HandoverError("handover is unapproved, completed, or claimed by another worker")


def complete(db, row, worker, next_id, report):
    if row["worker"] != worker or row["state"] not in ("claimed", "completed"):
        raise HandoverError("completion requires the original worker key")
    if row["state"] == "completed":
        child = db.execute("SELECT id, report FROM handovers WHERE parent_id = ?",
                           (row["id"],)).fetchone()
        if child is None or (child["id"], child["report"]) != (next_id, report):
            raise HandoverError("completion differs from the committed report")
        return dict(summary(row), next_id=next_id, replayed=True)
    if db.execute("SELECT 1 FROM handovers WHERE id = ?", (next_id,)).fetchone():
        raise HandoverError("follow-up ID already exists")
    add_report(db, next_id, report, row["id"])
    transition(db, row["id"], "completed")
    return {"id": row["id"], "state": "completed", "next_id": next_id, "replayed": False}


def run(db, args, data):
    command = args.command
    enabled = bool(db.execute("SELECT enabled FROM settings").fetchone()[0])
    if command == "mode":
        if args.value is not None and enabled != (args.value == "on"):
            enabled = args.value == "on"
            db.execute("UPDATE settings SET enabled = ?", (enabled,))
            event(db, None, "enabled" if enabled else "disabled")
        return {"enabled": enabled}
    if not enabled:
        raise HandoverError("ledger disabled")
    if command == "list":
        return [dict(row) for row in db.execute(
            "SELECT id, parent_id, state FROM handovers ORDER BY id")]
    if command == "events":
        return [dict(row) for row in db.execute("SELECT * FROM events ORDER BY sequence")]
    if command == "report":
        return publish_report(db, args.id, data)
    row = get(db, args.id)
    if command == "show":
        return {key: row[key] for key in row.keys() if key != "worker"}
    if command == "review":
        return review(db, row, data)
    if command == "decide":
        return decide(db, row, args.decision)
    if command == "claim":
        return claim(db, row, args.worker)
    return complete(db, row, args.worker, args.next_id, data)


def parse_args():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--db", required=True, type=Path, help="path to the local ledger")
    commands = parser.add_subparsers(dest="command", required=True)
    for command in ("init", "list", "events"):
        commands.add_parser(command)
    commands.add_parser("mode").add_argument("value", nargs="?", choices=("on", "off"))
    for command in ("report", "show", "review", "decide", "claim", "complete"):
        sub = commands.add_parser(command)
        sub.add_argument("id", type=identifier)
        if command == "decide":
            sub.add_argument("decision", choices=("approve", "reject"))
        if command in ("claim", "complete"):
            sub.add_argument("--worker", required=True, type=identifier)
        if command == "complete":
            sub.add_argument("next_id", type=identifier)
    return parser.parse_args()


def main():
    args = parse_args()
    try:
        if args.db.is_symlink():
            raise HandoverError("ledger path must not be a symbolic link")
        if args.command == "init":
            print(json.dumps(initialize(args.db)))
            return 0
        if not args.db.is_file():
            raise HandoverError("ledger file not found; initialize it explicitly")
        data = review_payload() if args.command == "review" else None
        if args.command in ("report", "complete"):
            data = payload()
        read_only = args.command in ("list", "show", "events") or (
            args.command == "mode" and args.value is None
        )
        mode = "ro" if read_only else "rw"
        uri = f"{args.db.resolve().as_uri()}?mode={mode}"
        with closing(sqlite3.connect(uri, uri=True, timeout=5)) as db, db:
            db.row_factory = sqlite3.Row
            db.execute("PRAGMA trusted_schema = OFF")
            db.execute("PRAGMA foreign_keys = ON")
            db.execute("BEGIN" if read_only else "BEGIN IMMEDIATE")
            if (db.execute("PRAGMA application_id").fetchone()[0] != APP_ID
                    or db.execute("PRAGMA user_version").fetchone()[0] != SCHEMA_VERSION):
                raise HandoverError("file is not a supported handover ledger")
            result = run(db, args, data)
        print(json.dumps(result))
        return 0
    except HandoverError as exc:
        print(f"handover: {exc}", file=sys.stderr)
    except FileExistsError:
        print("handover: ledger path already exists", file=sys.stderr)
    except (OSError, sqlite3.Error) as exc:
        code = getattr(exc, "sqlite_errorname", None) or type(exc).__name__
        print(f"handover: storage operation failed ({code})", file=sys.stderr)
    return 1


if __name__ == "__main__":
    sys.exit(main())

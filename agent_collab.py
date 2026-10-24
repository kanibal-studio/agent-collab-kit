"""Cooperative mail and exact-resource leases for a trusted local machine."""

__version__ = "0.1.2"

import argparse
from contextlib import contextmanager
import json
import math
import sqlite3
import sys
import time
import uuid


class Conflict(ValueError):
    """An existing message or lease conflicts with this request."""


def text_value(value, name):
    if not isinstance(value, str) or not value.strip() or "\x00" in value:
        raise ValueError(name + " must be a nonempty string without NUL")
    return value


def ttl_value(value):
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise ValueError("ttl must be numeric")
    if not math.isfinite(value) or not 0 < value <= 86400:
        raise ValueError("ttl must be finite, positive and <= 86400 seconds")
    return value


class Store:
    """Every mutating call uses one BEGIN IMMEDIATE transaction.

    clock is injectable for tests; production assumes a trusted wall clock.
    Opening requires an explicitly initialized database.
    """

    def __init__(self, db, clock=time.time):
        text_value(str(db), "db")
        self.clock = clock
        self.conn = sqlite3.connect(str(db), timeout=10, isolation_level=None)
        self.conn.row_factory = sqlite3.Row
        self.conn.execute("PRAGMA busy_timeout=10000")
        version = self.conn.execute("PRAGMA user_version").fetchone()[0]
        if version != 1:
            self.conn.close()
            raise ValueError("database is not initialized; run init")

    @staticmethod
    def initialize(db):
        text_value(str(db), "db")
        conn = sqlite3.connect(str(db), timeout=10, isolation_level=None)
        try:
            conn.execute("PRAGMA busy_timeout=10000")
            conn.execute("BEGIN IMMEDIATE")
            version = conn.execute("PRAGMA user_version").fetchone()[0]
            if version not in (0, 1):
                raise ValueError("unsupported database version")
            conn.execute("""CREATE TABLE IF NOT EXISTS messages (
                id TEXT PRIMARY KEY, idempotency_key TEXT NOT NULL UNIQUE,
                sender TEXT NOT NULL, recipient TEXT NOT NULL, body TEXT NOT NULL,
                created_at REAL NOT NULL, acknowledged_at REAL)""")
            conn.execute("""CREATE TABLE IF NOT EXISTS leases (
                resource TEXT PRIMARY KEY COLLATE BINARY, owner TEXT NOT NULL,
                generation TEXT NOT NULL, expires_at REAL NOT NULL)""")
            conn.execute("PRAGMA user_version=1")
            conn.execute("COMMIT")
        except Exception:
            if conn.in_transaction:
                conn.execute("ROLLBACK")
            raise
        finally:
            conn.close()

    def close(self):
        self.conn.close()

    def now(self):
        value = self.clock()
        if isinstance(value, bool) or not isinstance(value, (int, float)):
            raise ValueError("clock must return a finite number")
        if not math.isfinite(value):
            raise ValueError("clock must return a finite number")
        return value

    @contextmanager
    def transaction(self):
        self.conn.execute("BEGIN IMMEDIATE")
        try:
            yield
            self.conn.execute("COMMIT")
        except Exception:
            self.conn.execute("ROLLBACK")
            raise

    def send(self, sender, recipient, body, key):
        for name, value in (("sender", sender), ("recipient", recipient),
                            ("body", body), ("key", key)):
            text_value(value, name)
        with self.transaction():
            old = self.conn.execute(
                "SELECT * FROM messages WHERE idempotency_key=?", (key,)
            ).fetchone()
            if old is not None:
                if (old["sender"], old["recipient"], old["body"]) != (
                        sender, recipient, body):
                    raise Conflict("idempotency key has a different payload")
                return dict(old)
            identifier = str(uuid.uuid4())
            self.conn.execute(
                "INSERT INTO messages VALUES (?,?,?,?,?,?,NULL)",
                (identifier, key, sender, recipient, body, self.now()))
            return dict(self.conn.execute(
                "SELECT * FROM messages WHERE id=?", (identifier,)).fetchone())

    def inbox(self, recipient):
        text_value(recipient, "recipient")
        return [dict(row) for row in self.conn.execute(
            "SELECT * FROM messages WHERE recipient=? AND acknowledged_at IS NULL "
            "ORDER BY created_at, id", (recipient,))]

    def ack(self, identifier, recipient):
        text_value(identifier, "id")
        text_value(recipient, "recipient")
        with self.transaction():
            row = self.conn.execute(
                "SELECT * FROM messages WHERE id=? AND recipient=?",
                (identifier, recipient)).fetchone()
            if row is None:
                raise Conflict("message not found for recipient")
            if row["acknowledged_at"] is None:
                self.conn.execute(
                    "UPDATE messages SET acknowledged_at=? WHERE id=?",
                    (self.now(), identifier))
            return dict(self.conn.execute(
                "SELECT * FROM messages WHERE id=?", (identifier,)).fetchone())

    def claim(self, resource, owner, ttl):
        text_value(resource, "resource")
        text_value(owner, "owner")
        ttl_value(ttl)
        with self.transaction():
            now = self.now()
            row = self.conn.execute(
                "SELECT * FROM leases WHERE resource=?", (resource,)).fetchone()
            if row is not None and row["expires_at"] > now:
                raise Conflict("resource has an active lease")
            generation = str(uuid.uuid4())
            self.conn.execute("INSERT OR REPLACE INTO leases VALUES (?,?,?,?)",
                              (resource, owner, generation, now + ttl))
            return {"resource": resource, "owner": owner,
                    "generation": generation, "expires_at": now + ttl}

    def _owned(self, resource, owner, generation, now):
        for name, value in (("resource", resource), ("owner", owner),
                            ("generation", generation)):
            text_value(value, name)
        row = self.conn.execute(
            "SELECT * FROM leases WHERE resource=? AND owner=? AND generation=?",
            (resource, owner, generation)).fetchone()
        if row is None or row["expires_at"] <= now:
            raise Conflict("lease token does not identify an active lease")
        return row

    def renew(self, resource, owner, generation, ttl):
        ttl_value(ttl)
        with self.transaction():
            now = self.now()
            self._owned(resource, owner, generation, now)
            self.conn.execute("UPDATE leases SET expires_at=? WHERE resource=?",
                              (now + ttl, resource))
            return dict(self.conn.execute(
                "SELECT * FROM leases WHERE resource=?", (resource,)).fetchone())

    def release(self, resource, owner, generation):
        with self.transaction():
            self._owned(resource, owner, generation, self.now())
            self.conn.execute("DELETE FROM leases WHERE resource=?", (resource,))
            return {"released": resource}

    def leases(self):
        now = self.now()
        return [dict(row) for row in self.conn.execute(
            "SELECT * FROM leases WHERE expires_at>? ORDER BY resource", (now,))]


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--db", required=True, help="explicit local SQLite file")
    commands = parser.add_subparsers(dest="command", required=True)
    commands.add_parser("init")
    send = commands.add_parser("send")
    for name in ("sender", "recipient", "body", "key"):
        send.add_argument("--" + name, required=True)
    inbox = commands.add_parser("inbox")
    inbox.add_argument("--recipient", required=True)
    ack = commands.add_parser("ack")
    ack.add_argument("--id", required=True)
    ack.add_argument("--recipient", required=True)
    for command in ("claim", "renew", "release"):
        sub = commands.add_parser(command)
        sub.add_argument("--resource", required=True)
        sub.add_argument("--owner", required=True)
        if command != "claim":
            sub.add_argument("--generation", required=True)
        if command != "release":
            sub.add_argument("--ttl", required=True, type=float)
    commands.add_parser("leases")
    args = vars(parser.parse_args(argv))
    db, command = args.pop("db"), args.pop("command")
    store = None
    try:
        if command == "init":
            Store.initialize(db)
            result = {"initialized": db}
        else:
            store = Store(db)
            if command == "ack":
                args["identifier"] = args.pop("id")
            result = getattr(store, command)(**args)
        print(json.dumps(result, ensure_ascii=False))
        return 0
    except (ValueError, sqlite3.Error, OSError) as exc:
        print(str(exc), file=sys.stderr)
        return 1
    finally:
        if store is not None:
            store.close()


if __name__ == "__main__":
    sys.exit(main())

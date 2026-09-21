#!/usr/bin/env python3
"""Equipment inventory for one person's kit up to a full production fleet.

Single SQLite file, Python standard library only, every command scriptable and
`--json`-able so an agent can drive it. The design targets the two things that
actually make inventories rot: slow data entry (fixed by `scan`, which reads a
barcode wedge straight from stdin) and drift between the sheet and the shelf
(fixed by `audit`, a stocktake that reports missing and unexpected gear).

    python3 inventory.py init
    python3 inventory.py add --name "Sony FX6" --category CAM --owner STUDIO
    python3 inventory.py checkout CAM-0001 --to alice --days 3 --project "Spot Nike"
    python3 inventory.py scan --mode checkin --at SHELF-A

Run `python3 inventory.py --help` for the full command list.
"""

from __future__ import annotations

import argparse
import csv
import datetime as _dt
import json
import os
import sqlite3
import sys

SCHEMA_VERSION = 1
DEFAULT_DB = os.environ.get("GEAR_INVENTORY_DB", "inventory.db")

STATUSES = ("in_stock", "out", "repair", "lost", "retired")
CONDITIONS = ("new", "good", "worn", "damaged")
KINDS = ("unique", "bulk")

# Fields `set` and the CSV importer may write, in export order.
FIELDS = (
    "tag", "name", "category", "kind", "owner", "manufacturer", "model", "serial",
    "status", "condition", "location", "holder", "project", "due", "qty", "min_qty",
    "unit", "purchase_date", "purchase_price", "currency", "warranty_end",
    "insured_value", "maint_interval_days", "last_maint", "notes",
)
NUMERIC = {"qty", "min_qty", "purchase_price", "insured_value", "maint_interval_days"}

SCHEMA = """
CREATE TABLE meta (key TEXT PRIMARY KEY, value TEXT);

CREATE TABLE location (
    code TEXT PRIMARY KEY, name TEXT NOT NULL,
    kind TEXT NOT NULL DEFAULT 'room',   -- site | room | shelf | case | vehicle
    parent TEXT, note TEXT);

CREATE TABLE person (
    code TEXT PRIMARY KEY, name TEXT NOT NULL,
    email TEXT, team TEXT, active INTEGER NOT NULL DEFAULT 1);

CREATE TABLE asset (
    tag TEXT PRIMARY KEY,
    name TEXT NOT NULL,
    category TEXT,
    kind TEXT NOT NULL DEFAULT 'unique',
    owner TEXT,
    manufacturer TEXT, model TEXT, serial TEXT,
    status TEXT NOT NULL DEFAULT 'in_stock',
    condition TEXT NOT NULL DEFAULT 'good',
    location TEXT, holder TEXT, project TEXT, due TEXT,
    qty REAL NOT NULL DEFAULT 1,
    min_qty REAL NOT NULL DEFAULT 0,
    unit TEXT NOT NULL DEFAULT 'u',
    purchase_date TEXT, purchase_price REAL, currency TEXT,
    warranty_end TEXT, insured_value REAL,
    maint_interval_days INTEGER, last_maint TEXT,
    notes TEXT,
    created_at TEXT NOT NULL, updated_at TEXT NOT NULL);

CREATE TABLE kit (code TEXT PRIMARY KEY, name TEXT NOT NULL, notes TEXT);
CREATE TABLE kit_item (
    kit_code TEXT NOT NULL REFERENCES kit(code) ON DELETE CASCADE,
    tag TEXT NOT NULL REFERENCES asset(tag) ON DELETE CASCADE,
    qty REAL NOT NULL DEFAULT 1,
    PRIMARY KEY (kit_code, tag));

CREATE TABLE event (
    id INTEGER PRIMARY KEY,
    at TEXT NOT NULL, type TEXT NOT NULL, tag TEXT,
    person TEXT, location TEXT, project TEXT,
    qty REAL, due TEXT, note TEXT, actor TEXT);

CREATE TABLE maintenance (
    id INTEGER PRIMARY KEY, tag TEXT NOT NULL REFERENCES asset(tag) ON DELETE CASCADE,
    at TEXT NOT NULL, kind TEXT, cost REAL, vendor TEXT, note TEXT);

CREATE TABLE audit (
    code TEXT PRIMARY KEY, started TEXT NOT NULL, closed TEXT,
    scope TEXT, note TEXT);
CREATE TABLE audit_scan (
    audit_code TEXT NOT NULL REFERENCES audit(code) ON DELETE CASCADE,
    tag TEXT NOT NULL, at TEXT NOT NULL, location TEXT,
    PRIMARY KEY (audit_code, tag));

CREATE INDEX asset_status ON asset(status);
CREATE INDEX asset_location ON asset(location);
CREATE INDEX asset_holder ON asset(holder);
CREATE INDEX asset_category ON asset(category);
CREATE UNIQUE INDEX asset_serial ON asset(serial) WHERE serial IS NOT NULL AND serial <> '';
CREATE INDEX event_tag ON event(tag);
CREATE INDEX event_at ON event(at);
"""


class Error(Exception):
    """A problem the user can fix; printed without a traceback."""


# --- small helpers ----------------------------------------------------------


def now() -> str:
    return _dt.datetime.now().replace(microsecond=0).isoformat(sep=" ")


def today() -> str:
    return _dt.date.today().isoformat()


def parse_date(value: str) -> str:
    """Accept YYYY-MM-DD, or +N / -N days from today."""
    value = value.strip()
    if value and value[0] in "+-" and value[1:].isdigit():
        delta = _dt.timedelta(days=int(value))
        return (_dt.date.today() + delta).isoformat()
    try:
        return _dt.date.fromisoformat(value).isoformat()
    except ValueError:
        raise Error("bad date %r - use YYYY-MM-DD or +7 / -30" % value)


def days_between(a: str, b: str) -> int:
    return (_dt.date.fromisoformat(a) - _dt.date.fromisoformat(b)).days


def money(value, currency="") -> str:
    if value in (None, ""):
        return ""
    return ("%.2f %s" % (float(value), currency)).strip()


def connect(path: str, create: bool = False) -> sqlite3.Connection:
    if not create and not os.path.exists(path):
        raise Error("no inventory at %s - run `init` first (or pass --db)" % path)
    conn = sqlite3.connect(path)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    return conn


def log(conn, type_, tag=None, **kw) -> None:
    conn.execute(
        "INSERT INTO event (at, type, tag, person, location, project, qty, due, note,"
        " actor) VALUES (?,?,?,?,?,?,?,?,?,?)",
        (now(), type_, tag, kw.get("person"), kw.get("location"), kw.get("project"),
         kw.get("qty"), kw.get("due"), kw.get("note"),
         kw.get("actor") or os.environ.get("USER") or ""),
    )


def get_asset(conn, tag: str) -> sqlite3.Row:
    tag = tag.strip()
    row = conn.execute("SELECT * FROM asset WHERE tag = ?", (tag,)).fetchone()
    if row is None:
        row = conn.execute(
            "SELECT * FROM asset WHERE serial = ? AND serial <> ''", (tag,)
        ).fetchone()
    if row is None:
        raise Error("unknown tag %r" % tag)
    return row


def touch(conn, tag: str, **fields) -> None:
    fields["updated_at"] = now()
    sets = ", ".join("%s = ?" % k for k in fields)
    conn.execute("UPDATE asset SET %s WHERE tag = ?" % sets, (*fields.values(), tag))


def next_tag(conn, category: str) -> str:
    prefix = "".join(c for c in (category or "AST").upper() if c.isalnum())[:4] or "AST"
    rows = conn.execute(
        "SELECT tag FROM asset WHERE tag LIKE ?", (prefix + "-%",)
    ).fetchall()
    highest = 0
    for row in rows:
        suffix = row["tag"].rsplit("-", 1)[-1]
        if suffix.isdigit():
            highest = max(highest, int(suffix))
    return "%s-%04d" % (prefix, highest + 1)


def coerce(field: str, value):
    if value in (None, ""):
        return None if field in NUMERIC else value
    if field in NUMERIC:
        try:
            return int(value) if field == "maint_interval_days" else float(value)
        except ValueError:
            raise Error("%s must be a number, got %r" % (field, value))
    if field == "status" and value not in STATUSES:
        raise Error("status must be one of %s" % ", ".join(STATUSES))
    if field == "condition" and value not in CONDITIONS:
        raise Error("condition must be one of %s" % ", ".join(CONDITIONS))
    if field == "kind" and value not in KINDS:
        raise Error("kind must be one of %s" % ", ".join(KINDS))
    if field in ("due", "purchase_date", "warranty_end", "last_maint"):
        return parse_date(value)
    return value


# --- output -----------------------------------------------------------------


def emit(args, rows, headers=None) -> None:
    """Print rows as a table, JSON or CSV depending on the output flags."""
    dicts = [dict(r) for r in rows]
    if getattr(args, "json", False):
        print(json.dumps(dicts, ensure_ascii=False, indent=2, default=str))
        return
    if getattr(args, "csv", False):
        writer = csv.DictWriter(sys.stdout, fieldnames=headers or (dicts[0].keys() if dicts else []))
        writer.writeheader()
        writer.writerows(dicts)
        return
    if not dicts:
        print("(nothing)")
        return
    headers = headers or list(dicts[0].keys())
    widths = [
        max(len(str(h)), max(len(str(d.get(h, "") or "")) for d in dicts))
        for h in headers
    ]
    line = "  ".join(str(h).upper().ljust(w) for h, w in zip(headers, widths))
    print(line.rstrip())
    print("  ".join("-" * w for w in widths))
    for d in dicts:
        print("  ".join(str(d.get(h, "") or "").ljust(w) for h, w in zip(headers, widths)).rstrip())
    print("\n%d row(s)" % len(dicts))


def note(args, text: str) -> None:
    if not getattr(args, "json", False) and not getattr(args, "csv", False):
        print(text)


# --- commands: setup --------------------------------------------------------


def cmd_init(args) -> int:
    if os.path.exists(args.db) and not args.force:
        raise Error("%s already exists - pass --force to re-create it" % args.db)
    if args.force and os.path.exists(args.db):
        os.remove(args.db)
    conn = connect(args.db, create=True)
    conn.executescript(SCHEMA)
    conn.execute("INSERT INTO meta VALUES ('schema_version', ?)", (str(SCHEMA_VERSION),))
    conn.execute("INSERT INTO meta VALUES ('currency', ?)", (args.currency,))
    conn.execute("INSERT INTO meta VALUES ('created_at', ?)", (now(),))
    conn.commit()
    print("Created %s (schema v%d, currency %s)" % (args.db, SCHEMA_VERSION, args.currency))
    print("Next: `loc add`, `person add`, then `add` or `import`.")
    return 0


def cmd_loc(args) -> int:
    conn = connect(args.db)
    if args.loc_cmd == "add":
        conn.execute(
            "INSERT OR REPLACE INTO location (code, name, kind, parent, note)"
            " VALUES (?,?,?,?,?)",
            (args.code.upper(), args.name, args.kind, args.parent, args.note),
        )
        conn.commit()
        note(args, "location %s" % args.code.upper())
    elif args.loc_cmd == "rm":
        conn.execute("DELETE FROM location WHERE code = ?", (args.code.upper(),))
        conn.commit()
        note(args, "removed %s" % args.code.upper())
    else:
        rows = conn.execute(
            "SELECT l.code, l.name, l.kind, l.parent,"
            " (SELECT COUNT(*) FROM asset a WHERE a.location = l.code) AS assets"
            " FROM location l ORDER BY l.code"
        ).fetchall()
        emit(args, rows)
    return 0


def cmd_person(args) -> int:
    conn = connect(args.db)
    if args.person_cmd == "add":
        conn.execute(
            "INSERT OR REPLACE INTO person (code, name, email, team, active)"
            " VALUES (?,?,?,?,1)",
            (args.code.lower(), args.name, args.email, args.team),
        )
        conn.commit()
        note(args, "person %s" % args.code.lower())
    else:
        rows = conn.execute(
            "SELECT p.code, p.name, p.team, p.email,"
            " (SELECT COUNT(*) FROM asset a WHERE a.holder = p.code) AS holding"
            " FROM person p WHERE p.active = 1 ORDER BY p.code"
        ).fetchall()
        emit(args, rows)
    return 0


# --- commands: assets -------------------------------------------------------


def cmd_add(args) -> int:
    conn = connect(args.db)
    values = {"name": args.name, "category": args.category, "kind": args.kind}
    for field in FIELDS:
        got = getattr(args, field, None)
        if got is not None and field not in values:
            values[field] = coerce(field, got)
    tag = (args.tag or next_tag(conn, args.category)).strip().upper()
    if conn.execute("SELECT 1 FROM asset WHERE tag = ?", (tag,)).fetchone():
        raise Error("tag %s already exists" % tag)
    values["tag"] = tag
    values.setdefault("qty", 1 if args.kind == "unique" else 0)
    if args.location and not conn.execute(
        "SELECT 1 FROM location WHERE code = ?", (args.location.upper(),)
    ).fetchone():
        raise Error("unknown location %s - create it with `loc add`" % args.location)
    if args.location:
        values["location"] = args.location.upper()
    values["created_at"] = values["updated_at"] = now()
    columns = ", ".join(values)
    conn.execute(
        "INSERT INTO asset (%s) VALUES (%s)" % (columns, ",".join("?" * len(values))),
        tuple(values.values()),
    )
    log(conn, "create", tag, location=values.get("location"), note=args.name)
    conn.commit()
    if args.json:
        print(json.dumps(dict(get_asset(conn, tag)), ensure_ascii=False, indent=2))
    else:
        print("%s  %s" % (tag, args.name))
    return 0


def cmd_set(args) -> int:
    conn = connect(args.db)
    asset = get_asset(conn, args.tag)
    updates = {}
    for pair in args.assignments:
        if "=" not in pair:
            raise Error("expected field=value, got %r" % pair)
        field, value = pair.split("=", 1)
        field = field.strip()
        if field not in FIELDS or field == "tag":
            raise Error(
                "cannot set %r - settable fields: %s"
                % (field, ", ".join(f for f in FIELDS if f != "tag"))
            )
        updates[field] = coerce(field, value.strip())
    if not updates:
        raise Error("nothing to set")
    touch(conn, asset["tag"], **updates)
    log(conn, "edit", asset["tag"],
        note="; ".join("%s=%s" % (k, v) for k, v in updates.items()))
    conn.commit()
    note(args, "%s updated (%s)" % (asset["tag"], ", ".join(updates)))
    return 0


def _filters(args):
    where, params = [], []
    for field in ("status", "category", "owner", "kind", "holder", "project"):
        value = getattr(args, field, None)
        if value:
            where.append("%s = ?" % field)
            params.append(value)
    if getattr(args, "location", None):
        where.append("location = ?")
        params.append(args.location.upper())
    if getattr(args, "q", None):
        needle = "%%%s%%" % args.q.lower()
        where.append(
            "(LOWER(name) LIKE ? OR LOWER(tag) LIKE ? OR LOWER(COALESCE(model,'')) LIKE ?"
            " OR LOWER(COALESCE(serial,'')) LIKE ? OR LOWER(COALESCE(notes,'')) LIKE ?)"
        )
        params += [needle] * 5
    if getattr(args, "overdue", False):
        where.append("status = 'out' AND due IS NOT NULL AND due < ?")
        params.append(today())
    if not getattr(args, "all", False) and not getattr(args, "status", None):
        where.append("status <> 'retired'")
    return (" WHERE " + " AND ".join(where) if where else ""), params


def cmd_ls(args) -> int:
    conn = connect(args.db)
    clause, params = _filters(args)
    columns = args.fields.split(",") if args.fields else [
        "tag", "name", "category", "status", "location", "holder", "due", "qty",
    ]
    rows = conn.execute(
        "SELECT %s FROM asset%s ORDER BY %s" % (", ".join(columns), clause, args.sort),
        params,
    ).fetchall()
    emit(args, rows, columns)
    return 0


def cmd_show(args) -> int:
    conn = connect(args.db)
    asset = dict(get_asset(conn, args.tag))
    kits = [
        r["kit_code"]
        for r in conn.execute("SELECT kit_code FROM kit_item WHERE tag = ?", (asset["tag"],))
    ]
    asset["kits"] = ",".join(kits)
    if args.json:
        print(json.dumps(asset, ensure_ascii=False, indent=2, default=str))
        return 0
    width = max(len(k) for k in asset)
    for key, value in asset.items():
        if value not in (None, ""):
            print("%-*s  %s" % (width, key, value))
    history = conn.execute(
        "SELECT at, type, person, location, note FROM event WHERE tag = ?"
        " ORDER BY id DESC LIMIT 5", (asset["tag"],)
    ).fetchall()
    if history:
        print("\nlast events")
        for row in history:
            print("  %s  %-9s %s" % (row["at"], row["type"],
                                     row["person"] or row["location"] or row["note"] or ""))
    return 0


def cmd_history(args) -> int:
    conn = connect(args.db)
    asset = get_asset(conn, args.tag)
    rows = conn.execute(
        "SELECT at, type, person, location, project, qty, due, note, actor"
        " FROM event WHERE tag = ? ORDER BY id", (asset["tag"],)
    ).fetchall()
    emit(args, rows)
    return 0


def cmd_retire(args) -> int:
    conn = connect(args.db)
    asset = get_asset(conn, args.tag)
    if args.hard:
        conn.execute("DELETE FROM asset WHERE tag = ?", (asset["tag"],))
        log(conn, "delete", asset["tag"], note=args.reason)
    else:
        touch(conn, asset["tag"], status="retired", holder=None, due=None)
        log(conn, "retire", asset["tag"], note=args.reason)
    conn.commit()
    note(args, "%s %s" % (asset["tag"], "deleted" if args.hard else "retired"))
    return 0


# --- commands: movement -----------------------------------------------------


def _checkout_one(conn, tag, person, due, project, note_text, qty=None):
    asset = get_asset(conn, tag)
    if asset["status"] == "retired":
        raise Error("%s is retired" % asset["tag"])
    if asset["kind"] == "bulk":
        amount = qty if qty is not None else 1
        if asset["qty"] - amount < 0:
            raise Error("%s: only %g %s left" % (asset["tag"], asset["qty"], asset["unit"]))
        touch(conn, asset["tag"], qty=asset["qty"] - amount)
        log(conn, "checkout", asset["tag"], person=person, project=project, qty=amount,
            due=due, note=note_text)
        return "%s -%g %s (%g left)" % (asset["tag"], amount, asset["unit"],
                                        asset["qty"] - amount)
    if asset["status"] == "out":
        raise Error("%s is already out with %s" % (asset["tag"], asset["holder"] or "?"))
    if asset["status"] in ("repair", "lost"):
        raise Error("%s is marked %s" % (asset["tag"], asset["status"]))
    touch(conn, asset["tag"], status="out", holder=person, due=due, project=project)
    log(conn, "checkout", asset["tag"], person=person, project=project, due=due,
        note=note_text)
    return "%s -> %s%s" % (asset["tag"], person, " (due %s)" % due if due else "")


def _due_from(args):
    if args.due:
        return parse_date(args.due)
    if args.days:
        return parse_date("+%d" % args.days)
    return None


def cmd_checkout(args) -> int:
    conn = connect(args.db)
    if not conn.execute("SELECT 1 FROM person WHERE code = ?", (args.to.lower(),)).fetchone():
        raise Error("unknown person %r - add them with `person add`" % args.to)
    due = _due_from(args)
    results = []
    for tag in args.tags:
        results.append(_checkout_one(conn, tag, args.to.lower(), due, args.project,
                                     args.note, args.qty))
    conn.commit()
    for line in results:
        note(args, line)
    return 0


def _checkin_one(conn, tag, location, condition, note_text, qty=None):
    asset = get_asset(conn, tag)
    if asset["kind"] == "bulk":
        amount = qty if qty is not None else 1
        touch(conn, asset["tag"], qty=asset["qty"] + amount,
              **({"location": location} if location else {}))
        log(conn, "checkin", asset["tag"], location=location, qty=amount, note=note_text)
        return "%s +%g %s (%g on hand)" % (asset["tag"], amount, asset["unit"],
                                           asset["qty"] + amount)
    fields = {"status": "in_stock", "holder": None, "due": None, "project": None}
    if location:
        fields["location"] = location
    if condition:
        fields["condition"] = condition
        if condition == "damaged":
            fields["status"] = "repair"
    was = asset["holder"]
    touch(conn, asset["tag"], **fields)
    log(conn, "checkin", asset["tag"], person=was, location=location, note=note_text)
    late = ""
    if asset["due"] and asset["due"] < today():
        late = " (%d day(s) late)" % days_between(today(), asset["due"])
    return "%s back%s%s%s" % (asset["tag"], " from %s" % was if was else "",
                              " at %s" % location if location else "", late)


def cmd_checkin(args) -> int:
    conn = connect(args.db)
    location = args.at.upper() if args.at else None
    if location and not conn.execute(
        "SELECT 1 FROM location WHERE code = ?", (location,)
    ).fetchone():
        raise Error("unknown location %s" % location)
    results = [
        _checkin_one(conn, tag, location, args.condition, args.note, args.qty)
        for tag in args.tags
    ]
    conn.commit()
    for line in results:
        note(args, line)
    return 0


def cmd_move(args) -> int:
    conn = connect(args.db)
    location = args.to.upper()
    if not conn.execute("SELECT 1 FROM location WHERE code = ?", (location,)).fetchone():
        raise Error("unknown location %s" % location)
    for tag in args.tags:
        asset = get_asset(conn, tag)
        touch(conn, asset["tag"], location=location)
        log(conn, "move", asset["tag"], location=location, note=args.note)
        note(args, "%s -> %s" % (asset["tag"], location))
    conn.commit()
    return 0


def cmd_out(args) -> int:
    conn = connect(args.db)
    where = ["status = 'out'"]
    params = []
    if args.person:
        where.append("holder = ?")
        params.append(args.person.lower())
    if args.project:
        where.append("project = ?")
        params.append(args.project)
    if args.overdue:
        where.append("due IS NOT NULL AND due < ?")
        params.append(today())
    rows = conn.execute(
        "SELECT tag, name, holder, project, due,"
        " CASE WHEN due IS NOT NULL AND due < date('now','localtime') THEN 'LATE' ELSE '' END AS flag"
        " FROM asset WHERE %s ORDER BY due IS NULL, due, tag" % " AND ".join(where),
        params,
    ).fetchall()
    emit(args, rows)
    return 0


# --- commands: kits ---------------------------------------------------------


def cmd_kit(args) -> int:
    conn = connect(args.db)
    if args.kit_cmd == "new":
        conn.execute("INSERT OR REPLACE INTO kit (code, name, notes) VALUES (?,?,?)",
                     (args.code.upper(), args.name, args.note))
        conn.commit()
        note(args, "kit %s" % args.code.upper())
    elif args.kit_cmd == "add":
        code = args.code.upper()
        if not conn.execute("SELECT 1 FROM kit WHERE code = ?", (code,)).fetchone():
            raise Error("unknown kit %s - create it with `kit new`" % code)
        for tag in args.tags:
            asset = get_asset(conn, tag)
            conn.execute(
                "INSERT OR REPLACE INTO kit_item (kit_code, tag, qty) VALUES (?,?,?)",
                (code, asset["tag"], args.qty),
            )
            note(args, "%s + %s" % (code, asset["tag"]))
        conn.commit()
    elif args.kit_cmd == "rm":
        for tag in args.tags:
            conn.execute("DELETE FROM kit_item WHERE kit_code = ? AND tag = ?",
                         (args.code.upper(), tag.strip().upper()))
        conn.commit()
        note(args, "removed from %s" % args.code.upper())
    elif args.kit_cmd == "show":
        rows = conn.execute(
            "SELECT a.tag, a.name, ki.qty, a.status, a.holder, a.location"
            " FROM kit_item ki JOIN asset a ON a.tag = ki.tag"
            " WHERE ki.kit_code = ? ORDER BY a.tag", (args.code.upper(),)
        ).fetchall()
        emit(args, rows)
    elif args.kit_cmd in ("checkout", "checkin"):
        code = args.code.upper()
        items = conn.execute(
            "SELECT tag, qty FROM kit_item WHERE kit_code = ? ORDER BY tag", (code,)
        ).fetchall()
        if not items:
            raise Error("kit %s is empty" % code)
        if args.kit_cmd == "checkout":
            if not conn.execute("SELECT 1 FROM person WHERE code = ?",
                                (args.to.lower(),)).fetchone():
                raise Error("unknown person %r" % args.to)
            due = _due_from(args)
            blocked = [
                r["tag"] for r in conn.execute(
                    "SELECT a.tag FROM kit_item ki JOIN asset a ON a.tag = ki.tag"
                    " WHERE ki.kit_code = ? AND a.kind = 'unique'"
                    " AND a.status <> 'in_stock'", (code,))
            ]
            if blocked and not args.partial:
                raise Error(
                    "kit %s is not complete - unavailable: %s (use --partial to take"
                    " the rest)" % (code, ", ".join(blocked))
                )
            lines = []
            for item in items:
                if item["tag"] in blocked:
                    lines.append("%s SKIPPED (unavailable)" % item["tag"])
                    continue
                lines.append(_checkout_one(conn, item["tag"], args.to.lower(), due,
                                           args.project, args.note, item["qty"]))
            log(conn, "kit_checkout", None, person=args.to.lower(), project=args.project,
                due=due, note=code)
        else:
            location = args.at.upper() if args.at else None
            lines = []
            for item in items:
                asset = get_asset(conn, item["tag"])
                if asset["status"] != "out" and asset["kind"] != "bulk":
                    continue  # already back, or never went out
                lines.append(_checkin_one(conn, item["tag"], location, args.condition,
                                          args.note, item["qty"]))
            log(conn, "kit_checkin", None, location=location, note=code)
        conn.commit()
        for line in lines:
            note(args, line)
    else:
        rows = conn.execute(
            "SELECT k.code, k.name,"
            " (SELECT COUNT(*) FROM kit_item ki WHERE ki.kit_code = k.code) AS items,"
            " (SELECT COUNT(*) FROM kit_item ki JOIN asset a ON a.tag = ki.tag"
            "  WHERE ki.kit_code = k.code AND a.status = 'out') AS out"
            " FROM kit k ORDER BY k.code"
        ).fetchall()
        emit(args, rows)
    return 0


# --- commands: consumables --------------------------------------------------


def cmd_stock(args) -> int:
    conn = connect(args.db)
    if args.stock_cmd == "low":
        rows = conn.execute(
            "SELECT tag, name, qty, min_qty, unit, location, (min_qty - qty) AS shortfall"
            " FROM asset WHERE kind = 'bulk' AND status <> 'retired' AND qty <= min_qty"
            " ORDER BY shortfall DESC"
        ).fetchall()
        emit(args, rows)
        return 0
    asset = get_asset(conn, args.tag)
    if asset["kind"] != "bulk":
        raise Error("%s is a unique asset - use checkout/checkin" % asset["tag"])
    new = float(args.set) if args.set is not None else asset["qty"] + args.by
    if new < 0:
        raise Error("that would leave %g %s" % (new, asset["unit"]))
    touch(conn, asset["tag"], qty=new)
    log(conn, "adjust", asset["tag"], qty=new - asset["qty"], note=args.note)
    conn.commit()
    note(args, "%s  %g -> %g %s" % (asset["tag"], asset["qty"], new, asset["unit"]))
    return 0


# --- commands: maintenance --------------------------------------------------


def cmd_maint(args) -> int:
    conn = connect(args.db)
    if args.maint_cmd == "log":
        asset = get_asset(conn, args.tag)
        at = parse_date(args.date) if args.date else today()
        conn.execute(
            "INSERT INTO maintenance (tag, at, kind, cost, vendor, note)"
            " VALUES (?,?,?,?,?,?)",
            (asset["tag"], at, args.kind, args.cost, args.vendor, args.note),
        )
        fields = {"last_maint": at}
        if args.back_in_service and asset["status"] == "repair":
            fields["status"] = "in_stock"
        touch(conn, asset["tag"], **fields)
        log(conn, "maintenance", asset["tag"], note="%s %s" % (args.kind or "", args.note or ""))
        conn.commit()
        note(args, "%s serviced on %s" % (asset["tag"], at))
        return 0
    if args.maint_cmd == "history":
        rows = conn.execute(
            "SELECT at, kind, cost, vendor, note FROM maintenance WHERE tag = ?"
            " ORDER BY at", (get_asset(conn, args.tag)["tag"],)
        ).fetchall()
        emit(args, rows)
        return 0
    horizon = (_dt.date.today() + _dt.timedelta(days=args.days)).isoformat()
    rows = conn.execute(
        "SELECT tag, name, last_maint, maint_interval_days, status,"
        " date(COALESCE(last_maint, purchase_date, date('now')),"
        "      '+' || maint_interval_days || ' day') AS next_due"
        " FROM asset WHERE maint_interval_days IS NOT NULL AND maint_interval_days > 0"
        " AND status <> 'retired'"
        " AND date(COALESCE(last_maint, purchase_date, date('now')),"
        "          '+' || maint_interval_days || ' day') <= ?"
        " ORDER BY next_due", (horizon,)
    ).fetchall()
    emit(args, rows)
    return 0


# --- commands: stocktake ----------------------------------------------------


def _audit_scope_clause(scope):
    if not scope:
        return "", []
    if "=" not in scope:
        raise Error("scope must look like location=SHELF-A or category=CAM")
    field, value = scope.split("=", 1)
    if field not in ("location", "category", "owner", "holder"):
        raise Error("scope field must be location, category, owner or holder")
    return " AND %s = ?" % field, [value.upper() if field == "location" else value]


def cmd_audit(args) -> int:
    conn = connect(args.db)
    if args.audit_cmd == "new":
        code = args.code.upper()
        if conn.execute("SELECT 1 FROM audit WHERE code = ?", (code,)).fetchone():
            raise Error("audit %s already exists" % code)
        _audit_scope_clause(args.scope)  # validate early
        conn.execute("INSERT INTO audit (code, started, scope, note) VALUES (?,?,?,?)",
                     (code, now(), args.scope, args.note))
        conn.commit()
        note(args, "audit %s open - now scan with `scan --mode audit --audit %s`"
             % (code, code))
        return 0
    code = args.code.upper()
    audit = conn.execute("SELECT * FROM audit WHERE code = ?", (code,)).fetchone()
    if audit is None:
        raise Error("unknown audit %s" % code)
    if args.audit_cmd == "scan":
        seen = 0
        for tag in args.tags:
            asset = get_asset(conn, tag)
            conn.execute(
                "INSERT OR REPLACE INTO audit_scan (audit_code, tag, at, location)"
                " VALUES (?,?,?,?)", (code, asset["tag"], now(), asset["location"]))
            seen += 1
        conn.commit()
        note(args, "%d scanned into %s" % (seen, code))
        return 0
    # report
    clause, params = _audit_scope_clause(audit["scope"])
    expected = conn.execute(
        "SELECT tag, name, status, location, holder FROM asset"
        " WHERE status NOT IN ('retired','lost')%s ORDER BY tag" % clause, params
    ).fetchall()
    scanned = {r["tag"] for r in conn.execute(
        "SELECT tag FROM audit_scan WHERE audit_code = ?", (code,))}
    expected_tags = {r["tag"] for r in expected}
    missing = [dict(r, result="MISSING") for r in expected
               if r["tag"] not in scanned and r["status"] != "out"]
    out_not_seen = [dict(r, result="OUT (with %s)" % (r["holder"] or "?")) for r in expected
                    if r["tag"] not in scanned and r["status"] == "out"]
    back_unlogged = [dict(r, result="PRESENT BUT LOGGED OUT") for r in expected
                     if r["tag"] in scanned and r["status"] == "out"]
    unexpected = [
        dict(conn.execute("SELECT tag, name, status, location, holder FROM asset"
                          " WHERE tag = ?", (t,)).fetchone(), result="UNEXPECTED")
        for t in sorted(scanned - expected_tags)
    ]
    found = [dict(r, result="found") for r in expected
             if r["tag"] in scanned and r["status"] != "out"]
    rows = (missing + unexpected + back_unlogged + out_not_seen
            + (found if args.verbose else []))
    if args.close:
        conn.execute("UPDATE audit SET closed = ? WHERE code = ?", (now(), code))
        for row in missing:
            touch(conn, row["tag"], status="lost")
            log(conn, "lost", row["tag"], note="not found in audit %s" % code)
        conn.commit()
    emit(args, rows, ["tag", "name", "result", "location", "holder"])
    note(args, "expected %d / scanned %d / missing %d / unexpected %d /"
         " present but logged out %d%s"
         % (len(expected_tags), len(scanned), len(missing), len(unexpected),
            len(back_unlogged),
            " - closed, missing marked lost" if args.close else ""))
    return 0


# --- commands: scan wedge ---------------------------------------------------


def cmd_scan(args) -> int:
    """Read tags from stdin one per line - a USB barcode reader types them."""
    conn = connect(args.db)
    location = args.at.upper() if args.at else None
    if args.mode in ("checkout",) and not args.to:
        raise Error("--mode checkout needs --to PERSON")
    if args.mode == "move" and not args.to_location:
        raise Error("--mode move needs --to-location CODE")
    if args.mode == "audit" and not args.audit:
        raise Error("--mode audit needs --audit CODE")
    due = _due_from(args)
    interactive = sys.stdin.isatty()
    if interactive:
        print("mode=%s  scan tags, one per line, Ctrl-D to finish" % args.mode)
    ok = failed = 0
    for raw in sys.stdin:
        tag = raw.strip()
        if not tag or tag.startswith("#"):
            continue
        if tag.lower() in ("quit", "exit"):
            break
        try:
            if args.mode == "checkout":
                line = _checkout_one(conn, tag, args.to.lower(), due, args.project,
                                     args.note)
            elif args.mode == "checkin":
                line = _checkin_one(conn, tag, location, args.condition, args.note)
            elif args.mode == "move":
                asset = get_asset(conn, tag)
                touch(conn, asset["tag"], location=args.to_location.upper())
                log(conn, "move", asset["tag"], location=args.to_location.upper())
                line = "%s -> %s" % (asset["tag"], args.to_location.upper())
            elif args.mode == "audit":
                asset = get_asset(conn, tag)
                conn.execute(
                    "INSERT OR REPLACE INTO audit_scan (audit_code, tag, at, location)"
                    " VALUES (?,?,?,?)",
                    (args.audit.upper(), asset["tag"], now(), asset["location"]))
                line = "%s seen" % asset["tag"]
            else:  # info
                asset = get_asset(conn, tag)
                line = "%s  %s  %s%s" % (asset["tag"], asset["name"], asset["status"],
                                         " @%s" % asset["location"] if asset["location"] else "")
            conn.commit()
            ok += 1
            print("  OK  %s" % line)
        except Error as exc:
            failed += 1
            print("  ERR %s: %s" % (tag, exc), file=sys.stderr)
        sys.stdout.flush()
    print("\n%d ok, %d error(s)" % (ok, failed))
    return 1 if failed else 0


# --- commands: import / export ----------------------------------------------


def cmd_template(args) -> int:
    out = open(args.out, "w", newline="", encoding="utf-8") if args.out else sys.stdout
    writer = csv.writer(out)
    writer.writerow(FIELDS)
    writer.writerow([
        "CAM-0001", "Sony FX6", "CAM", "unique", "STUDIO", "Sony", "ILME-FX6V", "SN12345",
        "in_stock", "good", "SHELF-A", "", "", "", "1", "0", "u", "2024-03-01", "5900",
        "EUR", "2026-03-01", "5900", "180", "", "body only",
    ])
    writer.writerow([
        "BAT-0001", "Batteries V-Mount 95Wh", "BAT", "bulk", "STUDIO", "Core SWX", "", "",
        "in_stock", "good", "CASE-02", "", "", "", "12", "4", "u", "", "180", "EUR", "",
        "", "", "", "charge every 3 months",
    ])
    if args.out:
        out.close()
        print("wrote %s" % args.out)
    return 0


def cmd_import(args) -> int:
    conn = connect(args.db)
    with open(args.file, newline="", encoding="utf-8-sig") as handle:
        rows = list(csv.DictReader(handle))
    if not rows:
        raise Error("%s has no data rows" % args.file)
    unknown = set(rows[0]) - set(FIELDS)
    if unknown and not args.ignore_unknown:
        raise Error(
            "unknown column(s): %s - fix the header, or pass --ignore-unknown"
            % ", ".join(sorted(unknown))
        )
    known_locations = {r["code"] for r in conn.execute("SELECT code FROM location")}
    created = updated = skipped = 0
    problems = []
    for number, row in enumerate(rows, start=2):
        try:
            values = {}
            for field in FIELDS:
                if field in row and row[field].strip() != "":
                    values[field] = coerce(field, row[field].strip())
            if not values.get("name"):
                raise Error("name is required")
            location = values.get("location")
            if location:
                values["location"] = location.upper()
                if values["location"] not in known_locations:
                    if args.create_locations:
                        conn.execute("INSERT INTO location (code, name) VALUES (?,?)",
                                     (values["location"], values["location"]))
                        known_locations.add(values["location"])
                    else:
                        raise Error("unknown location %s (use --create-locations)"
                                    % values["location"])
            tag = (values.get("tag") or next_tag(conn, values.get("category"))).upper()
            values["tag"] = tag
            existing = conn.execute("SELECT 1 FROM asset WHERE tag = ?", (tag,)).fetchone()
            if existing and not args.update:
                skipped += 1
                continue
            if existing:
                fields = {k: v for k, v in values.items() if k != "tag"}
                if not args.dry_run:
                    touch(conn, tag, **fields)
                    log(conn, "import_update", tag)
                updated += 1
            else:
                values["created_at"] = values["updated_at"] = now()
                if not args.dry_run:
                    conn.execute(
                        "INSERT INTO asset (%s) VALUES (%s)"
                        % (", ".join(values), ",".join("?" * len(values))),
                        tuple(values.values()),
                    )
                    log(conn, "import_create", tag)
                created += 1
        except (Error, sqlite3.IntegrityError) as exc:
            problems.append("line %d: %s" % (number, exc))
            if not args.keep_going:
                conn.rollback()
                raise Error("%s (nothing was imported - fix it or pass --keep-going)"
                            % problems[-1])
    if args.dry_run:
        conn.rollback()
    else:
        conn.commit()
    for problem in problems:
        print("  skipped %s" % problem, file=sys.stderr)
    print("%s%d created, %d updated, %d already present, %d rejected"
          % ("dry run: " if args.dry_run else "", created, updated, skipped, len(problems)))
    return 1 if problems else 0


def cmd_export(args) -> int:
    conn = connect(args.db)
    clause, params = _filters(args)
    rows = conn.execute(
        "SELECT %s FROM asset%s ORDER BY tag" % (", ".join(FIELDS), clause), params
    ).fetchall()
    if args.out:
        with open(args.out, "w", newline="", encoding="utf-8") as handle:
            writer = csv.DictWriter(handle, fieldnames=FIELDS)
            writer.writeheader()
            writer.writerows(dict(r) for r in rows)
        print("wrote %d row(s) to %s" % (len(rows), args.out))
    else:
        args.csv = True
        emit(args, rows, list(FIELDS))
    return 0


# --- commands: reporting ----------------------------------------------------


def cmd_report(args) -> int:
    conn = connect(args.db)
    if args.report_cmd == "value":
        rows = conn.execute(
            "SELECT COALESCE(category,'(none)') AS category, COUNT(*) AS items,"
            " ROUND(SUM(COALESCE(purchase_price,0) * CASE WHEN kind='bulk' THEN qty ELSE 1 END),2)"
            "   AS purchase_value,"
            " ROUND(SUM(COALESCE(insured_value, purchase_price, 0)"
            "   * CASE WHEN kind='bulk' THEN qty ELSE 1 END),2) AS insured_value"
            " FROM asset WHERE status <> 'retired' GROUP BY category"
            " ORDER BY purchase_value DESC"
        ).fetchall()
        emit(args, rows)
        return 0
    if args.report_cmd == "by":
        field = args.field
        if field not in ("category", "status", "owner", "location", "holder", "condition"):
            raise Error("cannot group by %r" % field)
        rows = conn.execute(
            "SELECT COALESCE(%s,'(none)') AS %s, COUNT(*) AS items,"
            " ROUND(SUM(COALESCE(purchase_price,0)),2) AS value"
            " FROM asset WHERE status <> 'retired' GROUP BY %s ORDER BY items DESC"
            % (field, field, field)
        ).fetchall()
        emit(args, rows)
        return 0
    # summary
    one = lambda sql, *p: conn.execute(sql, p).fetchone()[0]
    data = {
        "assets": one("SELECT COUNT(*) FROM asset WHERE status <> 'retired'"),
        "unique_items": one("SELECT COUNT(*) FROM asset WHERE kind='unique' AND status<>'retired'"),
        "bulk_lines": one("SELECT COUNT(*) FROM asset WHERE kind='bulk' AND status<>'retired'"),
        "out": one("SELECT COUNT(*) FROM asset WHERE status='out'"),
        "overdue": one("SELECT COUNT(*) FROM asset WHERE status='out' AND due IS NOT NULL"
                       " AND due < date('now','localtime')"),
        "in_repair": one("SELECT COUNT(*) FROM asset WHERE status='repair'"),
        "lost": one("SELECT COUNT(*) FROM asset WHERE status='lost'"),
        "retired": one("SELECT COUNT(*) FROM asset WHERE status='retired'"),
        "low_stock": one("SELECT COUNT(*) FROM asset WHERE kind='bulk'"
                         " AND status<>'retired' AND qty <= min_qty"),
        "maintenance_due": one(
            "SELECT COUNT(*) FROM asset WHERE maint_interval_days > 0 AND status<>'retired'"
            " AND date(COALESCE(last_maint, purchase_date, date('now')),"
            " '+' || maint_interval_days || ' day') <= date('now','localtime')"),
        "purchase_value": one(
            "SELECT ROUND(COALESCE(SUM(COALESCE(purchase_price,0) *"
            " CASE WHEN kind='bulk' THEN qty ELSE 1 END),0),2)"
            " FROM asset WHERE status <> 'retired'"),
        "owners": one("SELECT COUNT(DISTINCT owner) FROM asset"
                      " WHERE owner IS NOT NULL AND owner <> ''"),
        "locations": one("SELECT COUNT(*) FROM location"),
        "people": one("SELECT COUNT(*) FROM person WHERE active = 1"),
        "kits": one("SELECT COUNT(*) FROM kit"),
    }
    if args.json:
        print(json.dumps(data, ensure_ascii=False, indent=2))
        return 0
    width = max(len(k) for k in data)
    for key, value in data.items():
        print("%-*s  %s" % (width, key, value))
    return 0


# --- commands: labels -------------------------------------------------------


def cmd_labels(args) -> int:
    sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
    import labels as labels_module

    conn = connect(args.db)
    clause, params = _filters(args)
    rows = conn.execute(
        "SELECT tag, name, category, owner, serial, location FROM asset%s ORDER BY tag"
        % clause, params
    ).fetchall()
    if args.tags:
        rows = [get_asset(conn, t) for t in args.tags]
    if not rows:
        raise Error("no assets matched - nothing to print")
    html = labels_module.sheet(
        [dict(r) for r in rows],
        url_base=args.url_base,
        columns=args.columns,
        rows_per_page=args.rows,
        barcode=args.barcode,
        subtitle_field=args.subtitle,
    )
    with open(args.out, "w", encoding="utf-8") as handle:
        handle.write(html)
    print("wrote %d label(s) to %s - open it in a browser and print at 100%% scale"
          % (len(rows), args.out))
    return 0


# --- argument parsing -------------------------------------------------------


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="inventory.py",
        description="Equipment inventory: personal kit to production fleet.",
    )
    parser.add_argument("--db", default=DEFAULT_DB,
                        help="SQLite file (default %(default)s, or $GEAR_INVENTORY_DB)")
    parser.add_argument("--json", action="store_true", help="machine-readable output")
    sub = parser.add_subparsers(dest="command", required=True)

    def add(name, help_, func):
        p = sub.add_parser(name, help=help_)
        p.set_defaults(func=func)
        return p

    p = add("init", "create a new inventory database", cmd_init)
    p.add_argument("--currency", default="EUR")
    p.add_argument("--force", action="store_true", help="overwrite an existing file")

    p = add("loc", "locations: sites, rooms, shelves, cases, vehicles", cmd_loc)
    s = p.add_subparsers(dest="loc_cmd", required=True)
    q = s.add_parser("add"); q.add_argument("code"); q.add_argument("name")
    q.add_argument("--kind", default="room",
                   choices=["site", "room", "shelf", "case", "vehicle"])
    q.add_argument("--parent"); q.add_argument("--note")
    q = s.add_parser("rm"); q.add_argument("code")
    s.add_parser("ls").add_argument("--csv", action="store_true")

    p = add("person", "people who can hold gear", cmd_person)
    s = p.add_subparsers(dest="person_cmd", required=True)
    q = s.add_parser("add"); q.add_argument("code"); q.add_argument("name")
    q.add_argument("--email"); q.add_argument("--team")
    s.add_parser("ls").add_argument("--csv", action="store_true")

    p = add("add", "register one asset", cmd_add)
    p.add_argument("--tag", help="printed label; generated from --category if omitted")
    p.add_argument("--name", required=True)
    p.add_argument("--category", help="short code such as CAM, LENS, AUDIO, LIGHT")
    p.add_argument("--kind", default="unique", choices=list(KINDS),
                   help="'bulk' for consumables counted by quantity")
    for field in ("owner", "manufacturer", "model", "serial", "location", "unit",
                  "currency", "notes", "purchase_date", "warranty_end", "condition"):
        p.add_argument("--" + field.replace("_", "-"), dest=field)
    for field in ("qty", "min_qty", "purchase_price", "insured_value",
                  "maint_interval_days"):
        p.add_argument("--" + field.replace("_", "-"), dest=field)

    p = add("set", "change fields: `set CAM-0001 condition=worn location=SHELF-B`", cmd_set)
    p.add_argument("tag"); p.add_argument("assignments", nargs="+", metavar="field=value")

    p = add("ls", "list assets", cmd_ls)
    for field in ("status", "category", "owner", "kind", "holder", "location", "project"):
        p.add_argument("--" + field)
    p.add_argument("-q", "--q", help="free-text search")
    p.add_argument("--overdue", action="store_true")
    p.add_argument("--all", action="store_true", help="include retired assets")
    p.add_argument("--fields", help="comma-separated columns")
    p.add_argument("--sort", default="tag")
    p.add_argument("--csv", action="store_true")

    p = add("show", "everything known about one asset", cmd_show)
    p.add_argument("tag")

    p = add("history", "full event log for one asset", cmd_history)
    p.add_argument("tag"); p.add_argument("--csv", action="store_true")

    p = add("retire", "retire (or --hard delete) an asset", cmd_retire)
    p.add_argument("tag"); p.add_argument("--reason"); p.add_argument("--hard", action="store_true")

    p = add("checkout", "hand gear to someone", cmd_checkout)
    p.add_argument("tags", nargs="+"); p.add_argument("--to", required=True)
    p.add_argument("--due"); p.add_argument("--days", type=int)
    p.add_argument("--project"); p.add_argument("--note")
    p.add_argument("--qty", type=float, help="for bulk items")

    p = add("checkin", "take gear back", cmd_checkin)
    p.add_argument("tags", nargs="+"); p.add_argument("--at", help="location code")
    p.add_argument("--condition", choices=list(CONDITIONS))
    p.add_argument("--note"); p.add_argument("--qty", type=float)

    p = add("move", "relocate gear without changing custody", cmd_move)
    p.add_argument("tags", nargs="+"); p.add_argument("--to", required=True)
    p.add_argument("--note")

    p = add("out", "what is currently out", cmd_out)
    p.add_argument("--person"); p.add_argument("--project")
    p.add_argument("--overdue", action="store_true"); p.add_argument("--csv", action="store_true")

    p = add("kit", "named bundles of gear that travel together", cmd_kit)
    s = p.add_subparsers(dest="kit_cmd", required=True)
    q = s.add_parser("new"); q.add_argument("code"); q.add_argument("name"); q.add_argument("--note")
    q = s.add_parser("add"); q.add_argument("code"); q.add_argument("tags", nargs="+")
    q.add_argument("--qty", type=float, default=1)
    q = s.add_parser("rm"); q.add_argument("code"); q.add_argument("tags", nargs="+")
    q = s.add_parser("show"); q.add_argument("code"); q.add_argument("--csv", action="store_true")
    q = s.add_parser("checkout"); q.add_argument("code"); q.add_argument("--to", required=True)
    q.add_argument("--due"); q.add_argument("--days", type=int); q.add_argument("--project")
    q.add_argument("--note"); q.add_argument("--partial", action="store_true")
    q = s.add_parser("checkin"); q.add_argument("code"); q.add_argument("--at")
    q.add_argument("--condition", choices=list(CONDITIONS)); q.add_argument("--note")
    s.add_parser("ls").add_argument("--csv", action="store_true")

    p = add("stock", "consumables: quantities and reorder levels", cmd_stock)
    s = p.add_subparsers(dest="stock_cmd", required=True)
    q = s.add_parser("adjust"); q.add_argument("tag")
    q.add_argument("--by", type=float, default=0); q.add_argument("--set")
    q.add_argument("--note")
    s.add_parser("low").add_argument("--csv", action="store_true")

    p = add("maint", "maintenance log and what is due", cmd_maint)
    s = p.add_subparsers(dest="maint_cmd", required=True)
    q = s.add_parser("log"); q.add_argument("tag"); q.add_argument("--kind")
    q.add_argument("--cost", type=float); q.add_argument("--vendor")
    q.add_argument("--note"); q.add_argument("--date")
    q.add_argument("--back-in-service", action="store_true")
    q = s.add_parser("history"); q.add_argument("tag"); q.add_argument("--csv", action="store_true")
    q = s.add_parser("due"); q.add_argument("--days", type=int, default=30)
    q.add_argument("--csv", action="store_true")

    p = add("audit", "physical stocktake: scan the shelf, compare to the books", cmd_audit)
    s = p.add_subparsers(dest="audit_cmd", required=True)
    q = s.add_parser("new"); q.add_argument("code")
    q.add_argument("--scope", help="limit to e.g. location=SHELF-A or category=CAM")
    q.add_argument("--note")
    q = s.add_parser("scan"); q.add_argument("code"); q.add_argument("tags", nargs="+")
    q = s.add_parser("report"); q.add_argument("code")
    q.add_argument("--close", action="store_true", help="close it and mark missing as lost")
    q.add_argument("--verbose", action="store_true", help="also list what was found")
    q.add_argument("--csv", action="store_true")

    p = add("scan", "barcode-wedge loop: reads tags from stdin", cmd_scan)
    p.add_argument("--mode", default="info",
                   choices=["info", "checkout", "checkin", "move", "audit"])
    p.add_argument("--to", help="person, for --mode checkout")
    p.add_argument("--to-location", help="location, for --mode move")
    p.add_argument("--at", help="location, for --mode checkin")
    p.add_argument("--audit", help="audit code, for --mode audit")
    p.add_argument("--due"); p.add_argument("--days", type=int)
    p.add_argument("--project"); p.add_argument("--note")
    p.add_argument("--condition", choices=list(CONDITIONS))

    p = add("import", "bulk-load assets from CSV", cmd_import)
    p.add_argument("file")
    p.add_argument("--update", action="store_true", help="update rows whose tag exists")
    p.add_argument("--dry-run", action="store_true")
    p.add_argument("--keep-going", action="store_true", help="skip bad rows instead of aborting")
    p.add_argument("--create-locations", action="store_true")
    p.add_argument("--ignore-unknown", action="store_true", help="ignore extra columns")

    p = add("export", "dump assets to CSV", cmd_export)
    for field in ("status", "category", "owner", "kind", "holder", "location", "project"):
        p.add_argument("--" + field)
    p.add_argument("-q", "--q"); p.add_argument("--all", action="store_true")
    p.add_argument("--out", help="file to write (default: stdout)")

    p = add("template", "write a CSV import template", cmd_template)
    p.add_argument("--out")

    p = add("report", "summary, value and breakdowns", cmd_report)
    s = p.add_subparsers(dest="report_cmd")
    s.add_parser("summary")
    s.add_parser("value").add_argument("--csv", action="store_true")
    q = s.add_parser("by"); q.add_argument("field"); q.add_argument("--csv", action="store_true")

    p = add("labels", "printable QR label sheet (HTML)", cmd_labels)
    p.add_argument("tags", nargs="*", help="specific tags; omit to use the filters")
    for field in ("status", "category", "owner", "kind", "location"):
        p.add_argument("--" + field)
    p.add_argument("-q", "--q")
    p.add_argument("--out", default="labels.html")
    p.add_argument("--columns", type=int, default=4)
    p.add_argument("--rows", type=int, default=10)
    p.add_argument("--url-base", help="encode BASE/TAG in the QR instead of the bare tag")
    p.add_argument("--barcode", choices=["none", "code39"], default="none",
                   help="add a 1D barcode for laser scanners")
    p.add_argument("--subtitle", default="name",
                   help="field printed under the tag (name, owner, serial...)")
    return parser


def main(argv=None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    for flag in ("json", "csv"):
        if not hasattr(args, flag):
            setattr(args, flag, False)
    if args.command == "report" and not getattr(args, "report_cmd", None):
        args.report_cmd = "summary"
    try:
        return args.func(args)
    except Error as exc:
        print("error: %s" % exc, file=sys.stderr)
        return 2
    except sqlite3.IntegrityError as exc:
        print("error: %s" % exc, file=sys.stderr)
        return 2
    except BrokenPipeError:
        return 0


if __name__ == "__main__":
    sys.exit(main())

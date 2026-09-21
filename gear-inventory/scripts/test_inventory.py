"""End-to-end tests for the inventory CLI - every test drives main().

The helper is called `cli` rather than `run`: TestCase.run is the runner's
own entry point and overriding it breaks collection.
"""

import contextlib
import io
import json
import os
import tempfile
import unittest

import inventory


class CliTest(unittest.TestCase):
    def setUp(self):
        self.dir = tempfile.TemporaryDirectory()
        self.addCleanup(self.dir.cleanup)
        self.db = os.path.join(self.dir.name, "t.db")
        self.cli("init")

    def cli(self, *args, stdin=None, expect=0):
        out, err = io.StringIO(), io.StringIO()
        real_stdin = inventory.sys.stdin
        if stdin is not None:
            inventory.sys.stdin = io.StringIO(stdin)
        try:
            with contextlib.redirect_stdout(out), contextlib.redirect_stderr(err):
                code = inventory.main(["--db", self.db, *args])
        finally:
            inventory.sys.stdin = real_stdin
        if expect is not None:
            self.assertEqual(
                code, expect, "exit %d for %s\n%s\n%s" % (code, args, out.getvalue(), err.getvalue())
            )
        return out.getvalue() + err.getvalue()

    def json_run(self, *args):
        out = io.StringIO()
        with contextlib.redirect_stdout(out):
            inventory.main(["--db", self.db, "--json", *args])
        return json.loads(out.getvalue())

    def seed(self):
        self.cli("loc", "add", "SHELF-A", "Shelf A", "--kind", "shelf")
        self.cli("loc", "add", "CASE-02", "Case 2", "--kind", "case")
        self.cli("person", "add", "alice", "Alice Martin", "--team", "camera")
        self.cli("person", "add", "bob", "Bob Diallo")
        self.cli("add", "--name", "Sony FX6", "--category", "CAM", "--owner", "STUDIO",
                 "--serial", "SN123", "--location", "SHELF-A", "--purchase-price", "5900")
        self.cli("add", "--name", "Sigma 24-70", "--category", "LENS",
                 "--owner", "STUDIO", "--location", "SHELF-A")
        self.cli("add", "--name", "Canon R5", "--category", "CAM", "--owner", "PERSO",
                 "--location", "CASE-02")
        self.cli("add", "--name", "V-Mount batteries", "--category", "BAT",
                 "--kind", "bulk", "--qty", "12", "--min-qty", "4",
                 "--location", "CASE-02")


class Setup(CliTest):
    def test_init_is_not_silently_destructive(self):
        self.assertIn("already exists", self.cli("init", expect=2))

    def test_commands_need_a_database(self):
        missing = os.path.join(self.dir.name, "none.db")
        out = io.StringIO()
        with contextlib.redirect_stderr(out):
            self.assertEqual(inventory.main(["--db", missing, "ls"]), 2)
        self.assertIn("run `init` first", out.getvalue())


class Assets(CliTest):
    def test_tags_are_generated_per_category(self):
        self.seed()
        tags = [a["tag"] for a in self.json_run("ls", "--sort", "tag")]
        self.assertEqual(tags, ["BAT-0001", "CAM-0001", "CAM-0002", "LENS-0001"])

    def test_explicit_tag_wins_and_collisions_are_refused(self):
        self.cli("add", "--name", "Tripod", "--tag", "TRI-9")
        self.assertIn("already exists",
                      self.cli("add", "--name", "Other", "--tag", "TRI-9", expect=2))

    def test_duplicate_serial_is_refused(self):
        self.seed()
        self.assertIn("error", self.cli("add", "--name", "Clone", "--category", "CAM",
                                        "--serial", "SN123", expect=2))

    def test_unknown_location_is_refused(self):
        self.assertIn("unknown location",
                      self.cli("add", "--name", "X", "--location", "NOWHERE", expect=2))

    def test_set_validates_the_field_and_the_value(self):
        self.seed()
        self.cli("set", "CAM-0001", "condition=worn", "notes=back focus drifts")
        asset = self.json_run("show", "CAM-0001")
        self.assertEqual(asset["condition"], "worn")
        self.assertIn("cannot set", self.cli("set", "CAM-0001", "colour=red", expect=2))
        self.assertIn("status must be",
                      self.cli("set", "CAM-0001", "status=broken", expect=2))

    def test_lookup_by_serial(self):
        self.seed()
        self.assertEqual(self.json_run("show", "SN123")["tag"], "CAM-0001")

    def test_retire_hides_from_the_default_listing(self):
        self.seed()
        self.cli("retire", "CAM-0002", "--reason", "sold")
        self.assertNotIn("CAM-0002", [a["tag"] for a in self.json_run("ls")])
        self.assertIn("CAM-0002", [a["tag"] for a in self.json_run("ls", "--all")])


class Custody(CliTest):
    def setUp(self):
        super().setUp()
        self.seed()

    def test_checkout_then_checkin(self):
        self.cli("checkout", "CAM-0001", "--to", "alice", "--days", "3",
                 "--project", "Spot Nike")
        asset = self.json_run("show", "CAM-0001")
        self.assertEqual((asset["status"], asset["holder"], asset["project"]),
                         ("out", "alice", "Spot Nike"))
        self.cli("checkin", "CAM-0001", "--at", "SHELF-A")
        asset = self.json_run("show", "CAM-0001")
        self.assertEqual(asset["status"], "in_stock")
        self.assertIsNone(asset["holder"])
        self.assertIsNone(asset["due"])

    def test_double_checkout_is_refused(self):
        self.cli("checkout", "CAM-0001", "--to", "alice")
        self.assertIn("already out",
                      self.cli("checkout", "CAM-0001", "--to", "bob", expect=2))

    def test_unknown_person_is_refused(self):
        self.assertIn("unknown person",
                      self.cli("checkout", "CAM-0001", "--to", "carol", expect=2))

    def test_overdue_is_reported(self):
        self.cli("checkout", "CAM-0001", "--to", "alice", "--due", "-2")
        late = self.json_run("out", "--overdue")
        self.assertEqual([r["tag"] for r in late], ["CAM-0001"])
        self.assertEqual(late[0]["flag"], "LATE")
        self.assertIn("day(s) late", self.cli("checkin", "CAM-0001"))

    def test_damaged_return_goes_to_repair(self):
        self.cli("checkout", "CAM-0001", "--to", "alice")
        self.cli("checkin", "CAM-0001", "--condition", "damaged")
        self.assertEqual(self.json_run("show", "CAM-0001")["status"], "repair")
        self.assertIn("is marked repair",
                      self.cli("checkout", "CAM-0001", "--to", "bob", expect=2))
        self.cli("maint", "log", "CAM-0001", "--kind", "sensor clean", "--cost", "120",
                 "--back-in-service")
        self.assertEqual(self.json_run("show", "CAM-0001")["status"], "in_stock")

    def test_move_keeps_custody(self):
        self.cli("checkout", "CAM-0001", "--to", "alice")
        self.cli("move", "CAM-0001", "--to", "CASE-02")
        asset = self.json_run("show", "CAM-0001")
        self.assertEqual((asset["location"], asset["holder"]), ("CASE-02", "alice"))

    def test_history_records_every_step(self):
        self.cli("checkout", "CAM-0001", "--to", "alice")
        self.cli("checkin", "CAM-0001")
        types = [e["type"] for e in self.json_run("history", "CAM-0001")]
        self.assertEqual(types, ["create", "checkout", "checkin"])


class Consumables(CliTest):
    def setUp(self):
        super().setUp()
        self.seed()

    def test_quantities_move_instead_of_custody(self):
        self.cli("checkout", "BAT-0001", "--to", "alice", "--qty", "4")
        self.assertEqual(self.json_run("show", "BAT-0001")["qty"], 8)
        self.cli("checkin", "BAT-0001", "--qty", "4")
        self.assertEqual(self.json_run("show", "BAT-0001")["qty"], 12)

    def test_cannot_take_more_than_is_on_hand(self):
        self.assertIn("only 12", self.cli("checkout", "BAT-0001", "--to", "alice",
                                          "--qty", "99", expect=2))

    def test_reorder_report(self):
        self.assertEqual(self.json_run("stock", "low"), [])
        self.cli("stock", "adjust", "BAT-0001", "--set", "3")
        low = self.json_run("stock", "low")
        self.assertEqual([(r["tag"], r["shortfall"]) for r in low], [("BAT-0001", 1)])

    def test_adjust_cannot_go_negative(self):
        self.assertIn("would leave",
                      self.cli("stock", "adjust", "BAT-0001", "--by", "-20", expect=2))

    def test_unique_assets_reject_stock_adjustments(self):
        self.assertIn("unique asset",
                      self.cli("stock", "adjust", "CAM-0001", "--by", "1", expect=2))


class Kits(CliTest):
    def setUp(self):
        super().setUp()
        self.seed()
        self.cli("kit", "new", "DOC-A", "Documentary kit")
        self.cli("kit", "add", "DOC-A", "CAM-0001", "LENS-0001")

    def test_incomplete_kit_blocks_checkout_unless_partial(self):
        self.cli("checkout", "LENS-0001", "--to", "bob")
        self.assertIn("not complete",
                      self.cli("kit", "checkout", "DOC-A", "--to", "alice", expect=2))
        self.assertEqual(self.json_run("show", "CAM-0001")["status"], "in_stock")
        out = self.cli("kit", "checkout", "DOC-A", "--to", "alice", "--partial")
        self.assertIn("SKIPPED", out)
        self.assertEqual(self.json_run("show", "CAM-0001")["holder"], "alice")

    def test_kit_round_trip(self):
        self.cli("kit", "checkout", "DOC-A", "--to", "alice", "--days", "2")
        self.assertEqual({r["tag"] for r in self.json_run("out")},
                         {"CAM-0001", "LENS-0001"})
        self.cli("kit", "checkin", "DOC-A", "--at", "SHELF-A")
        self.assertEqual(self.json_run("out"), [])

    def test_empty_kit_is_refused(self):
        self.cli("kit", "new", "EMPTY", "Nothing here")
        self.assertIn("is empty",
                      self.cli("kit", "checkout", "EMPTY", "--to", "alice", expect=2))


class Stocktake(CliTest):
    def setUp(self):
        super().setUp()
        self.seed()

    def test_report_classifies_every_discrepancy(self):
        self.cli("checkout", "CAM-0002", "--to", "alice")  # out, stays in CASE-02
        self.cli("audit", "new", "A1", "--scope", "location=CASE-02")
        self.cli("audit", "scan", "A1", "CAM-0002")  # on the shelf though logged out
        self.cli("audit", "scan", "A1", "CAM-0001")  # belongs to SHELF-A
        rows = {r["tag"]: r["result"] for r in self.json_run("audit", "report", "A1")}
        self.assertEqual(rows["CAM-0002"], "PRESENT BUT LOGGED OUT")
        self.assertEqual(rows["CAM-0001"], "UNEXPECTED")
        self.assertEqual(rows["BAT-0001"], "MISSING")

    def test_close_marks_missing_as_lost(self):
        self.cli("audit", "new", "A2", "--scope", "location=SHELF-A")
        self.cli("audit", "scan", "A2", "CAM-0001")
        self.cli("audit", "report", "A2", "--close")
        self.assertEqual(self.json_run("show", "LENS-0001")["status"], "lost")
        self.assertEqual(self.json_run("show", "CAM-0001")["status"], "in_stock")

    def test_bad_scope_is_refused_when_the_audit_is_opened(self):
        self.assertIn("scope must look like",
                      self.cli("audit", "new", "A3", "--scope", "shelf", expect=2))


class ScanMode(CliTest):
    def setUp(self):
        super().setUp()
        self.seed()

    def test_checkout_wedge(self):
        out = self.cli("scan", "--mode", "checkout", "--to", "alice", "--days", "1",
                       stdin="CAM-0001\n\nLENS-0001\n# a comment\n")
        self.assertIn("2 ok, 0 error", out)
        self.assertEqual(len(self.json_run("out")), 2)

    def test_bad_tags_are_reported_without_stopping_the_batch(self):
        out = self.cli("scan", "--mode", "checkin", "--at", "SHELF-A",
                       stdin="CAM-0001\nNOPE-1\n", expect=1)
        self.assertIn("unknown tag", out)
        self.assertIn("1 ok, 1 error", out)

    def test_audit_wedge_feeds_the_report(self):
        self.cli("audit", "new", "A9")
        self.cli("scan", "--mode", "audit", "--audit", "A9",
                 stdin="CAM-0001\nCAM-0002\nLENS-0001\nBAT-0001\n")
        self.assertEqual(self.json_run("audit", "report", "A9"), [])

    def test_missing_options_are_caught_before_scanning(self):
        self.assertIn("needs --to", self.cli("scan", "--mode", "checkout", expect=2))


class CsvRoundTrip(CliTest):
    def path(self, name):
        return os.path.join(self.dir.name, name)

    def write(self, name, text):
        with open(self.path(name), "w", encoding="utf-8") as handle:
            handle.write(text)
        return self.path(name)

    def test_import_creates_updates_and_dry_runs(self):
        self.cli("loc", "add", "SHELF-A", "Shelf A")
        csv_path = self.write("in.csv", (
            "tag,name,category,owner,location,purchase_price\n"
            "CAM-0001,Sony FX6,CAM,STUDIO,SHELF-A,5900\n"
            "CAM-0002,Canon R5,CAM,PERSO,SHELF-A,4000\n"
        ))
        self.assertIn("dry run: 2 created", self.cli("import", csv_path, "--dry-run"))
        self.assertEqual(self.json_run("ls"), [])
        self.cli("import", csv_path)
        self.assertEqual(len(self.json_run("ls")), 2)
        self.assertIn("2 already present", self.cli("import", csv_path))
        self.write("in.csv", "tag,name,condition\nCAM-0001,Sony FX6,worn\n")
        self.cli("import", csv_path, "--update")
        self.assertEqual(self.json_run("show", "CAM-0001")["condition"], "worn")

    def test_bad_input_is_rejected_whole(self):
        self.write("bad.csv", "tag,name,colour\nX-1,Thing,red\n")
        self.assertIn("unknown column", self.cli("import", self.path("bad.csv"), expect=2))
        self.write("bad2.csv", "tag,name,location\nX-1,Thing,GHOST\n")
        self.assertIn("unknown location",
                      self.cli("import", self.path("bad2.csv"), expect=2))
        self.assertEqual(self.json_run("ls"), [])
        self.cli("import", self.path("bad2.csv"), "--create-locations")
        self.assertEqual(self.json_run("show", "X-1")["location"], "GHOST")

    def test_keep_going_imports_the_good_rows(self):
        self.write("mix.csv", "tag,name,purchase_price\nA-1,Good,10\nA-2,Bad,abc\n")
        out = self.cli("import", self.path("mix.csv"), "--keep-going", expect=1)
        self.assertIn("1 created, 0 updated, 0 already present, 1 rejected", out)
        self.assertEqual([a["tag"] for a in self.json_run("ls")], ["A-1"])

    def test_export_round_trips_through_import(self):
        self.seed()
        self.cli("export", "--out", self.path("out.csv"))
        self.cli("init", "--force")
        self.cli("import", self.path("out.csv"), "--create-locations")
        self.assertEqual(len(self.json_run("ls")), 4)
        self.assertEqual(self.json_run("show", "CAM-0001")["serial"], "SN123")

    def test_template_is_importable_as_is(self):
        self.cli("template", "--out", self.path("tpl.csv"))
        self.cli("import", self.path("tpl.csv"), "--create-locations")
        self.assertEqual(len(self.json_run("ls")), 2)


class Reporting(CliTest):
    def test_summary_counts_and_value(self):
        self.seed()
        self.cli("checkout", "CAM-0001", "--to", "alice", "--due", "-1")
        data = self.json_run("report", "summary")
        self.assertEqual(data["assets"], 4)
        self.assertEqual((data["out"], data["overdue"]), (1, 1))
        self.assertEqual(data["owners"], 2)  # STUDIO and PERSO; the batteries have none
        self.assertEqual(data["purchase_value"], 5900)

    def test_group_by_rejects_arbitrary_columns(self):
        self.seed()
        self.assertEqual(
            {r["category"]: r["items"] for r in self.json_run("report", "by", "category")},
            {"CAM": 2, "LENS": 1, "BAT": 1},
        )
        self.assertIn("cannot group by", self.cli("report", "by", "notes", expect=2))

    def test_maintenance_due_uses_the_interval(self):
        self.cli("add", "--name", "Jib", "--category", "GRIP",
                 "--maint-interval-days", "30", "--purchase-date", "-90")
        self.assertEqual([r["tag"] for r in self.json_run("maint", "due")], ["GRIP-0001"])
        self.cli("maint", "log", "GRIP-0001", "--kind", "greased")
        # Serviced today, so nothing is overdue, but the next service is still
        # inside the default 30-day look-ahead window.
        self.assertEqual(self.json_run("maint", "due", "--days", "0"), [])
        self.assertEqual([r["tag"] for r in self.json_run("maint", "due")], ["GRIP-0001"])
        self.assertEqual(len(self.json_run("maint", "history", "GRIP-0001")), 1)


class Labels(CliTest):
    def test_sheet_has_one_qr_per_asset(self):
        self.seed()
        out_path = os.path.join(self.dir.name, "labels.html")
        self.cli("labels", "--category", "CAM", "--out", out_path, "--barcode", "code39")
        with open(out_path, encoding="utf-8") as handle:
            page = handle.read()
        self.assertEqual(page.count('class="qr"'), 2)
        self.assertEqual(page.count('class="c39"'), 2)
        self.assertIn("CAM-0001", page)
        self.assertNotIn("LENS-0001", page)

    def test_url_payloads_are_encoded(self):
        self.seed()
        import qrcode_min
        import labels as labels_module
        page = labels_module.sheet([{"tag": "CAM-0001", "name": "Sony FX6"}],
                                   url_base="https://inv.example/a")
        expected = qrcode_min.to_svg_path(qrcode_min.encode("https://inv.example/a/CAM-0001"))
        self.assertIn(expected, page)

    def test_empty_selection_is_an_error_not_an_empty_sheet(self):
        self.seed()
        self.assertIn("no assets matched",
                      self.cli("labels", "--category", "NOPE", expect=2))


if __name__ == "__main__":
    unittest.main(verbosity=1)

---
name: gear-inventory
description: Use when inventorying physical equipment - personal gear or a production fleet. Covers registering assets, QR/barcode labels, check-out and check-in to people and projects, kits, consumable stock levels, maintenance schedules, physical stocktakes (audits), CSV import/export and valuation reports. Triggers include "inventaire", "inventory", "matériel", "equipment", "asset tracking", "check-out", "stocktake", "parc matériel", "étiquettes QR", "gear list".
---

# Equipment Inventory

A dependency-free inventory that scales from one person's camera bag to a
multi-site production fleet. One SQLite file, one CLI, no server, no account.

```bash
python3 scripts/inventory.py init
python3 scripts/inventory.py --help
```

Every command takes `--db PATH` (or `$GEAR_INVENTORY_DB`, default
`./inventory.db`) and most take `--json` for machine-readable output. **Use
`--json` whenever you need to read a result back** - the human tables are for
the user, not for parsing.

## Deciding whether to build or buy

If the user has not chosen a tool yet, read
[references/tool-comparison.md](references/tool-comparison.md) first and give
them the honest trade-off. This CLI is the right answer for offline work, full
data ownership, agent-driven automation and zero per-seat cost. It is the wrong
answer if they need a phone app for a non-technical crew, reservation calendars
weeks ahead, or rental invoicing - point them at Shelf, Cheqroom or Rentman.

## The model, in one paragraph

An **asset** is one row, identified by a printed **tag** (`CAM-0001`). It is
either `unique` (tracked individually, has custody) or `bulk` (a consumable
tracked by quantity). Assets sit in a **location** (site, room, shelf, case,
vehicle), belong to an **owner** (which is what keeps personal gear separate
from company gear), and can be grouped into **kits** that travel together.
Handing gear to a **person** is a check-out; every state change is appended to
an immutable **event** log. An **audit** is a physical stocktake: scan the
shelf, then compare what you scanned to what the database expected.

## Workflow

1. **Set up** - `loc add`, `person add`. Locations are codes: `SHELF-A`,
   `CASE-02`, `VAN-1`.
2. **Load the gear** - `add` one at a time, or write a CSV from
   `templates/import-template.csv` and `import` it. `import --dry-run` first,
   always.
3. **Label it** - `labels --out labels.html`, print at 100% scale, stick, and
   scan one label to verify before printing the whole batch.
4. **Run it** - `checkout` / `checkin` / `move`, or `scan --mode …` with a
   barcode reader for anything over ~20 items.
5. **Keep it honest** - `audit` on a cadence, `maint due` monthly,
   `stock low` before each shoot.

## Commands worth knowing

| Need | Command |
|------|---------|
| Register gear | `add --name "Sony FX6" --category CAM --owner STUDIO` |
| Bulk load | `import gear.csv --dry-run` then `import gear.csv` |
| Print labels | `labels --category CAM --out labels.html` |
| Hand out gear | `checkout CAM-0001 LENS-0004 --to alice --days 3 --project "Spot Nike"` |
| Take it back | `checkin CAM-0001 --at SHELF-A --condition worn` |
| Fast bulk moves | `scan --mode checkin --at SHELF-A` (reads tags from stdin) |
| Whole kit at once | `kit checkout DOC-A --to alice --days 5` |
| What is out / late | `out --overdue` |
| Consumables | `stock adjust BAT-0001 --by -4`, `stock low` |
| Servicing | `maint due --days 30`, `maint log CAM-0001 --kind "sensor clean"` |
| Stocktake | `audit new INV-2026Q3 --scope location=SHELF-A` → `scan --mode audit --audit INV-2026Q3` → `audit report INV-2026Q3` |
| Value / insurance | `report value`, `export --out inventory.csv` |
| One item's life | `show CAM-0001`, `history CAM-0001` |

## Golden rules

1. **Never invent a tag or a serial number.** Ask, or read it off the gear. A
   wrong serial is worse than a missing one - it breaks insurance claims.
2. **`import --dry-run` before every import.** The importer rejects the whole
   file on the first bad row unless `--keep-going` is passed; that is
   deliberate, so a malformed export cannot half-load.
3. **Tags are permanent.** Rename anything else; never re-tag an asset, because
   the printed label and the event history both point at the tag.
4. **One owner field, one truth.** Personal gear gets `--owner PERSO` (or the
   person's name), company gear the entity that bought it. Mixing them is how
   people end up insuring gear they sold.
5. **Do not mark things lost casually.** `audit report --close` flips every
   unscanned item to `lost`. Run the report without `--close` first, look at
   it, then close.
6. **Consumables are `--kind bulk`.** Batteries, gaffer tape, SD cards by the
   dozen. Custody makes no sense for them; quantity does.
7. **Ask before destructive work.** `retire --hard` and `init --force` delete
   data. Retiring (the default) keeps the history.

## Reference files

- [references/tool-comparison.md](references/tool-comparison.md) - build vs buy,
  with what the market charges in 2026.
- [references/method.md](references/method.md) - tag schemes, categories, audit
  cadence, and what changes when the fleet grows past a few hundred items.
- [references/labeling.md](references/labeling.md) - QR vs barcode vs RFID,
  label materials, printing, and where to stick them on a camera.
- [references/cli.md](references/cli.md) - every command and flag.
- [GUIDE-FR.md](GUIDE-FR.md) - guide de démarrage en français.

## Common mistakes

| Mistake | Fix |
|---------|-----|
| `error: no inventory at inventory.db` | Run `init`, or point `--db` at the real file |
| `unknown location SHELF-A` | Locations must exist first: `loc add SHELF-A "Shelf A"` |
| `unknown person alice` | `person add alice "Alice Martin"` |
| Import rejects the whole file | Read the line number it printed; `--dry-run` shows every problem without writing |
| Labels print too small | Print at 100% / "actual size", margins off; lower `--columns` for bigger tags |
| QR will not scan | Printed under ~15 mm, or on a curved/shiny surface - reprint bigger and flat |
| Audit says everything is MISSING | The scope is wrong (`--scope location=X`) or you scanned into a different audit code |

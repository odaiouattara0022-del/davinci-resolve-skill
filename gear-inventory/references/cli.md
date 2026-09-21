# CLI reference

`python3 scripts/inventory.py [--db PATH] [--json] COMMAND ...`

- `--db PATH` - the SQLite file. Defaults to `$GEAR_INVENTORY_DB`, then
  `./inventory.db`.
- `--json` - machine-readable output. Available on every listing and on `show`,
  `history`, `report`. Listings also take `--csv`.
- Exit codes: `0` success, `1` finished with rejected rows or failed scans,
  `2` the command was wrong (unknown tag, bad value, missing database).

Dates accept `YYYY-MM-DD` or a relative `+7` / `-30` (days from today).

## Setup

| Command | Notes |
|---------|-------|
| `init [--currency EUR] [--force]` | Creates the database. `--force` deletes an existing one. |
| `loc add CODE NAME [--kind site\|room\|shelf\|case\|vehicle] [--parent] [--note]` | Codes are upper-cased. |
| `loc ls` / `loc rm CODE` | `ls` shows how many assets sit in each. |
| `person add CODE NAME [--email] [--team]` | Codes are lower-cased. |
| `person ls` | Shows how many items each person holds. |

## Assets

| Command | Notes |
|---------|-------|
| `add --name NAME [--tag] [--category] [--kind unique\|bulk] [--owner] [--manufacturer] [--model] [--serial] [--location] [--qty] [--min-qty] [--unit] [--purchase-date] [--purchase-price] [--currency] [--warranty-end] [--insured-value] [--maint-interval-days] [--condition] [--notes]` | Tag is generated from `--category` when omitted. Serial numbers must be unique. |
| `set TAG field=value ...` | Any field except `tag`. Validates statuses, conditions, dates and numbers. |
| `ls [--status] [--category] [--owner] [--kind] [--holder] [--location] [--project] [-q TEXT] [--overdue] [--all] [--fields a,b,c] [--sort COL]` | Hides retired assets unless `--all` or an explicit `--status`. |
| `show TAG` | Everything known, plus the last five events. Accepts a serial number instead of a tag. |
| `history TAG` | The full event log. |
| `retire TAG [--reason] [--hard]` | Default keeps the row and its history; `--hard` deletes it. |

## Custody

| Command | Notes |
|---------|-------|
| `checkout TAG... --to PERSON [--due DATE\|--days N] [--project] [--note] [--qty N]` | Refuses gear that is already out, in repair or lost. `--qty` for bulk. |
| `checkin TAG... [--at LOCATION] [--condition] [--note] [--qty N]` | `--condition damaged` sends it to `repair`. Reports how late it was. |
| `move TAG... --to LOCATION [--note]` | Changes location without touching custody. |
| `out [--person] [--project] [--overdue]` | What is out, late ones flagged `LATE`. |

## Kits

| Command | Notes |
|---------|-------|
| `kit new CODE NAME [--note]` | |
| `kit add CODE TAG... [--qty N]` / `kit rm CODE TAG...` | |
| `kit ls` / `kit show CODE` | `ls` shows how many items of each kit are out. |
| `kit checkout CODE --to PERSON [--due\|--days] [--project] [--partial]` | Refuses an incomplete kit unless `--partial`. |
| `kit checkin CODE [--at] [--condition]` | Only touches the items that are actually out. |

## Consumables

| Command | Notes |
|---------|-------|
| `stock adjust TAG [--by N] [--set N] [--note]` | `--by` is relative (negative to consume), `--set` absolute. Refuses to go below zero. |
| `stock low` | Everything at or below its `min_qty`, worst shortfall first. |

## Maintenance

| Command | Notes |
|---------|-------|
| `maint log TAG [--kind] [--cost] [--vendor] [--note] [--date] [--back-in-service]` | Sets `last_maint`; `--back-in-service` returns it from `repair` to stock. |
| `maint history TAG` | |
| `maint due [--days 30]` | Based on `maint_interval_days` from the last service (or purchase date). `--days 0` = overdue only. |

## Stocktake

| Command | Notes |
|---------|-------|
| `audit new CODE [--scope FIELD=VALUE] [--note]` | Scope on `location`, `category`, `owner` or `holder`. No scope = whole fleet. |
| `audit scan CODE TAG...` | Or use `scan --mode audit`. |
| `audit report CODE [--close] [--verbose]` | `--close` marks everything still missing as `lost`. Run it once without first. |

## Barcode wedge

`scan --mode info|checkout|checkin|move|audit [--to] [--at] [--to-location] [--audit] [--due|--days] [--project] [--note] [--condition]`

Reads one tag per line from stdin - which is exactly what a USB barcode reader
types - until EOF, `quit`, or `exit`. Blank lines and `#` comments are skipped.
Each line prints `OK` or `ERR` and is committed immediately, so an
unrecognised tag never costs you the rest of the batch. Exits `1` if anything
failed.

```bash
python3 scripts/inventory.py scan --mode checkout --to alice --days 2
python3 scripts/inventory.py scan --mode checkin --at SHELF-A < returned.txt
```

## Data in and out

| Command | Notes |
|---------|-------|
| `template [--out FILE]` | A CSV with the right header and two example rows. |
| `import FILE [--update] [--dry-run] [--keep-going] [--create-locations] [--ignore-unknown]` | Aborts on the first bad row by default, so a bad file cannot half-load. |
| `export [filters] [--out FILE]` | Same columns as the template; prints to stdout without `--out`. |

## Reporting and labels

| Command | Notes |
|---------|-------|
| `report summary` | Counts, overdue, low stock, maintenance due, total purchase value. |
| `report value` | Purchase and insured value per category. |
| `report by FIELD` | Group by `category`, `status`, `owner`, `location`, `holder` or `condition`. |
| `labels [TAG...] [filters] [--out labels.html] [--columns 4] [--rows 10] [--barcode none\|code39] [--url-base URL] [--subtitle FIELD]` | HTML sheet of QR labels. See [labeling.md](labeling.md). |

## Schema

Tables: `asset`, `location`, `person`, `kit`, `kit_item`, `event`,
`maintenance`, `audit`, `audit_scan`, `meta`. Plain SQLite - query it directly
when the CLI does not have the report you want:

```bash
sqlite3 inventory.db "SELECT holder, COUNT(*) FROM asset WHERE status='out' GROUP BY holder"
```

Asset statuses: `in_stock`, `out`, `repair`, `lost`, `retired`.
Conditions: `new`, `good`, `worn`, `damaged`. Kinds: `unique`, `bulk`.

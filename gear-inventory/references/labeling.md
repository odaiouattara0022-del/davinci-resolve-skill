# Labels: QR, barcode, RFID

## Which technology

| | QR / 2D | 1D barcode (Code 39) | Passive UHF RFID |
|---|---|---|---|
| Scanner | any phone camera | cheap USB laser reader | handheld reader, ~$1,500-3,500 |
| Speed | one at a time, ~1 s | one at a time, ~0.3 s | 200-1,000+ tags/second, no line of sight |
| Tag cost at volume | ~$0.02-0.05 printed | ~$0.02-0.05 printed | ~$0.05-1.00 per tag |
| Fixed infrastructure | none | none | readers/portals, ~$1,000-3,000 each |
| Survives a small label | down to ~12-15 mm | needs length, poor on small gear | tag size is the constraint |

Figures from the 2026 comparisons linked in
[tool-comparison.md](tool-comparison.md); treat them as orders of magnitude.

**Rule of thumb.** Under ~500 items, QR only - the scanning hardware is a phone
you already own. Over a few thousand items, or if a full stocktake takes more
than a day, RFID pays for itself in labour within about a year; keep printing
QR alongside it, because a human still has to read the tag when the reader is
in the van.

`labels.py` prints QR by default and adds Code 39 with `--barcode code39`. RFID
is out of scope for this toolchain: encode the same tag string into the RFID
tag's EPC field and keep this database as the source of truth.

## Printing

```bash
python3 scripts/inventory.py labels --category CAM --out labels.html
python3 scripts/inventory.py labels --out all.html --columns 3 --rows 8
python3 scripts/inventory.py labels CAM-0001 CAM-0002 --out two.html
```

Open the file in a browser and print **at 100% / "actual size", margins off**.
Scaling to fit is what makes QR codes unreadable. `--columns` and `--rows`
match the sheet you actually have - 4x10 is close to a standard 48.5x25.4 mm
Avery layout, 3x8 gives bigger tags for flight cases.

Print one sheet on plain paper first, scan a label with your phone, then commit
to the label stock.

## Payload

By default the QR contains the bare tag (`CAM-0007`), which is what the `scan`
command expects on stdin. With `--url-base https://inv.example/a` it encodes
`https://inv.example/a/CAM-0007` instead, so a phone camera opens a page - only
useful if you actually host something at that URL. The bare tag is the safer
default: it never rots.

## Materials and placement

- **Indoors, light use**: laser-printed paper labels with a clear laminate
  patch over them. Cheapest, and fine on shelves and cases.
- **Cameras, lenses, anything handled daily**: polyester or vinyl labels, not
  paper. Paper peels at the corner within weeks and takes the QR with it.
- **Cable and small accessories**: wrap-around flag labels, printed twice so
  one side always faces out. A QR wrapped around a 6 mm cable will not scan.
- **Outdoors, wet, or road cases**: engraved or printed-on-metal plates, or
  accept re-labelling once a year.

Placement matters more than material: put the label where it is visible
**without unpacking** - the outside of the case, the bottom plate of a camera,
the barrel end of a lens. If someone has to lift the gear to scan it, the
inventory will drift.

Keep a small spare-label stock of the same tags. A label that falls off in the
field is the most common cause of an "unexpected" line in an audit report.

## Re-tagging

Don't. The tag is the primary key, it is printed on the gear, and the event
history hangs off it. If a label is damaged, reprint the *same* tag:

```bash
python3 scripts/inventory.py labels CAM-0007 --out reprint.html
```

"""Printable asset-label sheets as a self-contained HTML file.

HTML rather than PDF on purpose: no dependencies, every machine has a browser,
and the browser's print dialog handles paper size and margins. Print at 100% /
"actual size" with margins off, on plain A4 or on a matching Avery-style sheet.

    import labels
    open("labels.html", "w").write(labels.sheet(assets))

Each label carries a QR code (any phone camera reads it), the tag in large
mono type, and one subtitle line. `barcode="code39"` adds a 1D barcode for
cheap laser scanners, which are still the fastest way to check in 200 items.
"""

from __future__ import annotations

import html

import qrcode_min

# Code 39: 9 elements per character (bar, space, bar, ... bar), 'w' = wide.
CODE39 = {
    "0": "nnnwwnwnn", "1": "wnnwnnnnw", "2": "nnwwnnnnw", "3": "wnwwnnnnn",
    "4": "nnnwwnnnw", "5": "wnnwwnnnn", "6": "nnwwwnnnn", "7": "nnnwnnwnw",
    "8": "wnnwnnwnn", "9": "nnwwnnwnn", "A": "wnnnnwnnw", "B": "nnwnnwnnw",
    "C": "wnwnnwnnn", "D": "nnnnwwnnw", "E": "wnnnwwnnn", "F": "nnwnwwnnn",
    "G": "nnnnnwwnw", "H": "wnnnnwwnn", "I": "nnwnnwwnn", "J": "nnnnwwwnn",
    "K": "wnnnnnnww", "L": "nnwnnnnww", "M": "wnwnnnnwn", "N": "nnnnwnnww",
    "O": "wnnnwnnwn", "P": "nnwnwnnwn", "Q": "nnnnnnwww", "R": "wnnnnnwwn",
    "S": "nnwnnnwwn", "T": "nnnnwnwwn", "U": "wwnnnnnnw", "V": "nwwnnnnnw",
    "W": "wwwnnnnnn", "X": "nwnnwnnnw", "Y": "wwnnwnnnn", "Z": "nwwnwnnnn",
    "-": "nwnnnnwnw", ".": "wwnnnnwnn", " ": "nwwnnnwnn", "$": "nwnwnwnnn",
    "/": "nwnwnnnwn", "+": "nwnnnwnwn", "%": "nnnwnwnwn", "*": "nwnnwnwnn",
}

NARROW = 1.0
WIDE = 3.0


def code39_svg(text: str, height: float = 34.0, module: float = 1.1) -> str:
    """Code 39 barcode as an inline SVG. Unsupported characters are dropped."""
    text = "".join(c for c in text.upper() if c in CODE39 and c != "*")
    if not text:
        return ""
    x, bars = 0.0, []
    for index, char in enumerate("*" + text + "*"):
        if index:
            x += NARROW  # inter-character gap
        for position, element in enumerate(CODE39[char]):
            width = WIDE if element == "w" else NARROW
            if position % 2 == 0:  # even positions are bars
                bars.append('<rect x="%g" y="0" width="%g" height="%g"/>'
                            % (x * module, width * module, height))
            x += width
    return (
        '<svg class="c39" viewBox="0 0 %g %g" width="100%%" height="%g" '
        'preserveAspectRatio="none" xmlns="http://www.w3.org/2000/svg">%s</svg>'
        % (x * module, height, height, "".join(bars))
    )


def qr_svg(payload: str, size: int = 96) -> str:
    """QR code as an inline SVG with the mandatory 4-module quiet zone."""
    matrix = qrcode_min.encode(payload)
    modules = len(matrix) + 8
    return (
        '<svg class="qr" viewBox="0 0 %d %d" width="%d" height="%d" '
        'xmlns="http://www.w3.org/2000/svg" shape-rendering="crispEdges">'
        '<rect width="%d" height="%d" fill="#fff"/>'
        '<g transform="translate(4,4)"><path d="%s" fill="#000"/></g></svg>'
        % (modules, modules, size, size, modules, modules,
           qrcode_min.to_svg_path(matrix))
    )


CSS = """
:root { --gap: 2mm; }
* { box-sizing: border-box; }
body { margin: 0; font-family: "Helvetica Neue", Arial, sans-serif; color: #000;
       background: #fff; }
.sheet { display: grid; grid-template-columns: repeat(%(columns)d, 1fr);
         gap: var(--gap); padding: 6mm; page-break-after: always; }
.label { border: 0.2mm solid #bbb; border-radius: 1.5mm; padding: 2mm;
         display: grid; grid-template-columns: auto 1fr; gap: 2mm;
         align-items: center; min-height: %(height)gmm; overflow: hidden; }
.qr { display: block; }
.text { min-width: 0; }
.tag { font-family: "SF Mono", Menlo, Consolas, monospace; font-weight: 700;
       font-size: %(tag_size)gpt; letter-spacing: -0.2pt; line-height: 1.05;
       word-break: break-all; }
.sub { font-size: 7pt; line-height: 1.2; margin-top: 0.8mm; color: #222;
       display: -webkit-box; -webkit-line-clamp: 2; -webkit-box-orient: vertical;
       overflow: hidden; }
.meta { font-size: 5.5pt; color: #666; margin-top: 0.6mm; }
.c39 { margin-top: 1mm; display: block; }
@media print {
  .hint { display: none; }
  .label { border-color: #ddd; }
  @page { size: A4; margin: 0; }
}
.hint { font: 11px/1.5 system-ui, sans-serif; background: #fffbe6;
        border-bottom: 1px solid #e8d98a; padding: 8px 12px; color: #4a4000; }
"""

PAGE = """<!doctype html>
<meta charset="utf-8">
<title>%(title)s</title>
<style>%(css)s</style>
<div class="hint">%(count)d label(s). Print at 100%% scale ("actual size"),
margins off. Scan one test label before printing the whole batch.</div>
%(sheets)s
"""


def sheet(assets, url_base=None, columns=4, rows_per_page=10, barcode="none",
          subtitle_field="name", title="Asset labels") -> str:
    """Build the HTML sheet. `assets` is a list of dicts with at least `tag`."""
    per_page = max(1, columns * rows_per_page)
    height = max(12.0, (277.0 / max(1, rows_per_page)) - 2.5)
    tag_size = 13 if columns <= 3 else (11 if columns == 4 else 9)
    pages = []
    for start in range(0, len(assets), per_page):
        cells = []
        for asset in assets[start : start + per_page]:
            tag = str(asset.get("tag", "")).strip()
            payload = "%s/%s" % (url_base.rstrip("/"), tag) if url_base else tag
            subtitle = str(asset.get(subtitle_field) or "")
            meta = " · ".join(
                str(asset[k]) for k in ("owner", "location") if asset.get(k)
            )
            cells.append(
                '<div class="label">%s<div class="text"><div class="tag">%s</div>'
                '<div class="sub">%s</div>%s%s</div></div>'
                % (
                    qr_svg(payload, size=int(height * 2.6)),
                    html.escape(tag),
                    html.escape(subtitle),
                    '<div class="meta">%s</div>' % html.escape(meta) if meta else "",
                    code39_svg(tag) if barcode == "code39" else "",
                )
            )
        pages.append('<div class="sheet">%s</div>' % "".join(cells))
    return PAGE % {
        "title": html.escape(title),
        "css": CSS % {"columns": columns, "height": height, "tag_size": tag_size},
        "count": len(assets),
        "sheets": "\n".join(pages),
    }


if __name__ == "__main__":
    import sys

    tags = sys.argv[1:] or ["CAM-0001", "LENS-0042", "BAT-0007"]
    print(sheet([{"tag": t, "name": t, "owner": "STUDIO"} for t in tags]))

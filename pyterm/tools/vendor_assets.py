#!/usr/bin/env python3
"""Rapatrie CodeMirror et Pyodide dans pyterm/vendor/, puis pointe l'interface
dessus. Apres cela, PyTerm ne depend plus d'aucun CDN : tout est servi par
votre hebergement, ce qui rend l'isolation du site triviale a satisfaire et
le premier chargement plus rapide.

    python3 pyterm/tools/vendor_assets.py                    # coeur seul
    python3 pyterm/tools/vendor_assets.py --packages numpy,pandas
    python3 pyterm/tools/vendor_assets.py --restore          # revenir au CDN

Le coeur de Pyodide pese environ 12 Mo ; chaque paquet ajoute quelques Mo.
Seule la bibliotheque standard est necessaire pour demarrer : les paquets ne
servent que si vous voulez qu'ils fonctionnent hors connexion.
"""

from __future__ import annotations

import argparse
import json
import shutil
import sys
import urllib.error
import urllib.request
from pathlib import Path

APP = Path(__file__).resolve().parent.parent
VENDOR = APP / "vendor"
INDEX = APP / "index.html"
BACKUP = APP / "index.html.cdn"

CM_VERSION = "5.65.16"
CM_BASE = "https://cdnjs.cloudflare.com/ajax/libs/codemirror/%s/"
CM_FILES = [
    "codemirror.min.css",
    "codemirror.min.js",
    "mode/python/python.min.js",
    "mode/markdown/markdown.min.js",
    "mode/javascript/javascript.min.js",
    "addon/edit/matchbrackets.min.js",
    "addon/edit/closebrackets.min.js",
    "addon/comment/comment.min.js",
    "addon/search/searchcursor.min.js",
    "addon/selection/active-line.min.js",
    "addon/hint/show-hint.min.js",
    "addon/hint/anyword-hint.min.js",
]

PY_VERSION = "0.26.4"
PY_BASE = "https://cdn.jsdelivr.net/pyodide/v%s/full/"
# Le coeur strict ; les fichiers optionnels ne font pas echouer le script.
PY_CORE = ["pyodide.js", "pyodide.asm.js", "pyodide.asm.wasm",
           "python_stdlib.zip", "pyodide-lock.json"]
PY_OPTIONAL = ["pyodide.mjs", "pyodide.asm.data", "package.json"]

MARKER = "window.PYTERM_PYODIDE_URL"


# --------------------------------------------------------------------------
# Telechargement
# --------------------------------------------------------------------------

def fetch(url: str, attempts: int = 3) -> bytes:
    last: Exception | None = None
    for n in range(attempts):
        try:
            request = urllib.request.Request(url, headers={"User-Agent": "PyTerm-vendor"})
            with urllib.request.urlopen(request, timeout=120) as response:
                return response.read()
        except Exception as exc:                      # reseau : on retente
            last = exc
    raise RuntimeError("echec du telechargement de %s : %s" % (url, last))


def save(target: Path, payload: bytes) -> None:
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_bytes(payload)
    size = len(payload)
    unit = "%d o" % size if size < 1024 else (
        "%.0f Ko" % (size / 1024) if size < 1024 * 1024 else "%.1f Mo" % (size / 1048576))
    print("    %-42s %10s" % (target.relative_to(APP), unit))


def grab(base: str, name: str, root: Path, optional: bool = False) -> bool:
    try:
        save(root / name, fetch(base + name))
        return True
    except RuntimeError as exc:
        if optional:
            print("    (ignore) %s" % name)
            return False
        raise exc


# --------------------------------------------------------------------------
# Paquets Pyodide
# --------------------------------------------------------------------------

def resolve_packages(lock: dict, wanted: list[str]) -> list[str]:
    """Ferme la liste demandee sur ses dependances, via pyodide-lock.json."""
    catalogue = lock.get("packages", {})
    by_name = {name.lower(): name for name in catalogue}
    seen: set[str] = set()
    queue = list(wanted)
    missing: list[str] = []

    while queue:
        raw = queue.pop().strip().lower()
        if not raw or raw in seen:
            continue
        key = by_name.get(raw)
        if key is None:
            missing.append(raw)
            continue
        seen.add(raw)
        queue.extend(d.lower() for d in catalogue[key].get("depends", []))

    if missing:
        print("  paquets inconnus de cette version de Pyodide : %s" % ", ".join(sorted(missing)))
    return sorted(catalogue[by_name[name]]["file_name"] for name in seen)


# --------------------------------------------------------------------------
# Reecriture de l'interface
# --------------------------------------------------------------------------

def to_local(html: str) -> str:
    """Fait pointer index.html sur vendor/ au lieu des CDN."""
    cm_base = CM_BASE % CM_VERSION
    for name in CM_FILES:
        html = html.replace(cm_base + name, "vendor/codemirror/" + name)
    # Les preconnexions vers les CDN n'ont plus lieu d'etre.
    for host in ("https://cdnjs.cloudflare.com", "https://cdn.jsdelivr.net"):
        html = html.replace('<link rel="preconnect" href="%s">\n' % host, "")
    if MARKER not in html:
        html = html.replace(
            '<script src="js/platform.js"></script>',
            '<script>%s = "vendor/pyodide/";</script>\n'
            '<script src="js/platform.js"></script>' % MARKER)
    return html


def count_local(html: str) -> tuple[int, int]:
    local = sum(1 for name in CM_FILES if "vendor/codemirror/" + name in html)
    return local, len(CM_FILES)


# --------------------------------------------------------------------------

def restore() -> int:
    if not BACKUP.is_file():
        print("aucune sauvegarde : index.html n'a pas ete modifie par ce script.")
        return 1
    shutil.copy2(BACKUP, INDEX)
    BACKUP.unlink()
    if VENDOR.is_dir():
        shutil.rmtree(VENDOR)
    print("index.html restaure, dossier vendor/ supprime : retour au CDN.")
    return 0


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(
        description="Heberge CodeMirror et Pyodide avec l'application.")
    parser.add_argument("--packages", default="",
                        help="paquets Pyodide a inclure, separes par des virgules")
    parser.add_argument("--pyodide-version", default=PY_VERSION)
    parser.add_argument("--codemirror-version", default=CM_VERSION)
    parser.add_argument("--restore", action="store_true",
                        help="revenir aux CDN et effacer vendor/")
    parser.add_argument("--skip-pyodide", action="store_true",
                        help="ne rapatrier que CodeMirror (interface legere)")
    args = parser.parse_args(argv)

    if args.restore:
        return restore()

    if not INDEX.is_file():
        print("index.html introuvable — lancez le script depuis le depot.", file=sys.stderr)
        return 1

    cm_base = CM_BASE % args.codemirror_version
    py_base = PY_BASE % args.pyodide_version

    print("CodeMirror %s" % args.codemirror_version)
    for name in CM_FILES:
        grab(cm_base, name, VENDOR / "codemirror")

    if not args.skip_pyodide:
        print("Pyodide %s" % args.pyodide_version)
        for name in PY_CORE:
            grab(py_base, name, VENDOR / "pyodide")
        for name in PY_OPTIONAL:
            grab(py_base, name, VENDOR / "pyodide", optional=True)

        wanted = [p for p in args.packages.split(",") if p.strip()]
        if wanted:
            lock = json.loads((VENDOR / "pyodide" / "pyodide-lock.json").read_text())
            files = resolve_packages(lock, wanted)
            print("  %d fichier(s) de paquets, dependances comprises" % len(files))
            for name in files:
                grab(py_base, name, VENDOR / "pyodide", optional=True)

    if not BACKUP.is_file():
        shutil.copy2(INDEX, BACKUP)
    html = to_local(INDEX.read_text(encoding="utf-8"))
    INDEX.write_text(html, encoding="utf-8")

    done, total = count_local(html)
    print("\nindex.html pointe sur vendor/ (%d/%d fichiers CodeMirror)." % (done, total))
    if not args.skip_pyodide:
        print("Pyodide sera charge depuis vendor/pyodide/.")
    total_size = sum(f.stat().st_size for f in VENDOR.rglob("*") if f.is_file())
    print("vendor/ : %.1f Mo. Televersez le dossier complet sur votre hebergement."
          % (total_size / 1048576))
    print("Pour revenir en arriere : python3 tools/vendor_assets.py --restore")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

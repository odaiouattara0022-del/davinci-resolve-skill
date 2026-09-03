#!/usr/bin/env python3
"""Noyau CPython local pour PyTerm — bibliotheque standard uniquement.

Il rend deux services a la fois :

1. Il sert l'interface (le dossier ``pyterm/``) avec les en-tetes d'isolation
   qui debloquent, cote navigateur, la saisie clavier en direct et le Ctrl+C
   du moteur Pyodide.
2. Il expose un vrai interpreteur CPython — celui de la machine, avec ses
   sockets, son ``pip`` et son disque — que l'interface pilote a distance.

Utilisation ::

    python3 server/kernel.py                 # ouvre http://127.0.0.1:8777
    python3 server/kernel.py --port 9000
    python3 server/kernel.py --workdir ~/py  # dossier de travail des scripts
    python3 server/kernel.py --host 0.0.0.0 --token secret   # depuis le telephone

Sur Android, le meme fichier fonctionne sous Termux (``pkg install python``).

Attention : ce service execute le code qu'il recoit. Il n'ecoute que sur
127.0.0.1 par defaut ; toute autre adresse exige ``--token``.
"""

from __future__ import annotations

import argparse
import ast
import builtins
import ctypes
import io
import json
import os
import platform
import queue
import subprocess
import sys
import threading
import time
import traceback
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import urlparse, parse_qs

APP_DIR = Path(__file__).resolve().parent.parent
MAX_BODY = 8 * 1024 * 1024
FLUSH_INTERVAL = 0.04
FLUSH_SIZE = 8192


# --------------------------------------------------------------------------
# Diffusion des evenements vers les navigateurs connectes (SSE)
# --------------------------------------------------------------------------

class Broadcaster:
    """Distribue les evenements a tous les flux /events ouverts."""

    def __init__(self) -> None:
        self._clients: list[queue.Queue] = []
        self._lock = threading.Lock()

    def subscribe(self) -> queue.Queue:
        q: queue.Queue = queue.Queue(maxsize=4096)
        with self._lock:
            self._clients.append(q)
        return q

    def unsubscribe(self, q: queue.Queue) -> None:
        with self._lock:
            if q in self._clients:
                self._clients.remove(q)

    def send(self, event: dict) -> None:
        payload = json.dumps(event, ensure_ascii=False)
        with self._lock:
            clients = list(self._clients)
        for q in clients:
            try:
                q.put_nowait(payload)
            except queue.Full:
                pass  # client trop lent : on preserve l'interpreteur

    @property
    def count(self) -> int:
        with self._lock:
            return len(self._clients)


BUS = Broadcaster()


class StreamWriter(io.TextIOBase):
    """sys.stdout / sys.stderr : regroupe les ecritures avant diffusion."""

    def __init__(self, channel: str) -> None:
        self.channel = channel
        self._buf: list[str] = []
        self._size = 0
        self._last = time.monotonic()
        self._lock = threading.Lock()

    def write(self, text) -> int:  # type: ignore[override]
        if not isinstance(text, str):
            text = str(text)
        if not text:
            return 0
        with self._lock:
            self._buf.append(text)
            self._size += len(text)
            due = self._size >= FLUSH_SIZE or (time.monotonic() - self._last) >= FLUSH_INTERVAL
        if due or "\n" in text:
            self.flush()
        return len(text)

    def flush(self) -> None:  # type: ignore[override]
        with self._lock:
            if not self._buf:
                return
            data = "".join(self._buf)
            self._buf = []
            self._size = 0
            self._last = time.monotonic()
        BUS.send({"type": self.channel, "data": data})

    def writable(self) -> bool:  # type: ignore[override]
        return True

    def isatty(self) -> bool:  # type: ignore[override]
        return False


class StreamReader(io.TextIOBase):
    """sys.stdin : reclame une ligne a l'interface et attend la reponse."""

    def __init__(self) -> None:
        self.queue: queue.Queue = queue.Queue()
        self.pending: list[str] = []

    def prime(self, lines) -> None:
        self.pending = [str(x) for x in (lines or [])]
        while not self.queue.empty():
            try:
                self.queue.get_nowait()
            except queue.Empty:
                break

    def readline(self, size=-1) -> str:  # type: ignore[override]
        if self.pending:
            return self.pending.pop(0).rstrip("\n") + "\n"
        sys.stdout.flush()
        BUS.send({"type": "stdin"})
        value = self.queue.get()
        if value is None:
            return ""
        return str(value).rstrip("\n") + "\n"

    def read(self, size=-1) -> str:  # type: ignore[override]
        chunks = []
        while True:
            line = self.readline()
            if not line:
                break
            chunks.append(line)
        return "".join(chunks)

    def readable(self) -> bool:  # type: ignore[override]
        return True

    def isatty(self) -> bool:  # type: ignore[override]
        return False


# --------------------------------------------------------------------------
# Interpreteur
# --------------------------------------------------------------------------

class Kernel:
    """Un espace de noms persistant, execute dans un thread dedie."""

    def __init__(self, workdir: Path) -> None:
        self.workdir = workdir
        self.ns: dict = {"__name__": "__main__", "__doc__": None}
        self.stdout = StreamWriter("stdout")
        self.stderr = StreamWriter("stderr")
        self.stdin = StreamReader()
        self.thread: threading.Thread | None = None
        self.lock = threading.Lock()

    # -- utilitaires -------------------------------------------------------

    @staticmethod
    def _lineno(exc: BaseException, filename: str) -> int:
        tb, line = exc.__traceback__, 0
        while tb is not None:
            if tb.tb_frame.f_code.co_filename == filename:
                line = tb.tb_lineno
            tb = tb.tb_next
        return line

    def reset(self) -> None:
        self.ns.clear()
        self.ns.update({"__name__": "__main__", "__doc__": None})

    def busy(self) -> bool:
        return self.thread is not None and self.thread.is_alive()

    # -- execution ---------------------------------------------------------

    def submit(self, code: str, echo: bool, filename: str, stdin_lines) -> bool:
        if self.busy():
            return False
        self.stdin.prime(stdin_lines)
        self.thread = threading.Thread(
            target=self._run, args=(code, echo, filename), daemon=True,
            name="pyterm-exec")
        self.thread.start()
        return True

    def _run(self, code: str, echo: bool, filename: str) -> None:
        started = time.monotonic()
        old = (sys.stdout, sys.stderr, sys.stdin)
        sys.stdout, sys.stderr, sys.stdin = self.stdout, self.stderr, self.stdin
        result = {"ok": True, "value": None}
        try:
            os.chdir(self.workdir)
            result = self._exec(code, echo, filename)
        except BaseException as exc:  # garde-fou : le thread ne doit pas mourir muet
            traceback.print_exc()
            result = {"ok": False, "type": type(exc).__name__, "msg": str(exc), "line": 0}
        finally:
            self.stdout.flush()
            self.stderr.flush()
            sys.stdout, sys.stderr, sys.stdin = old
            BUS.send({
                "type": "done",
                "result": result,
                "ms": int((time.monotonic() - started) * 1000),
            })

    def _exec(self, source: str, echo: bool, filename: str) -> dict:
        try:
            tree = ast.parse(source, filename=filename, mode="exec")
        except SyntaxError as exc:
            traceback.print_exception(SyntaxError, exc, None)
            return {"ok": False, "type": "SyntaxError",
                    "msg": exc.msg or "erreur de syntaxe", "line": exc.lineno or 0}

        body = list(tree.body)
        tail = body.pop() if (echo and body and isinstance(body[-1], ast.Expr)) else None
        try:
            if body:
                exec(compile(ast.Module(body=body, type_ignores=[]), filename, "exec"), self.ns)
            value = None
            if tail is not None:
                outcome = eval(compile(ast.Expression(tail.value), filename, "eval"), self.ns)
                if outcome is not None:
                    builtins._ = outcome
                    try:
                        value = repr(outcome)
                    except Exception:
                        value = "<objet dont repr() a echoue>"
            return {"ok": True, "value": value}
        except SystemExit as exc:
            return {"ok": True, "exit": 0 if exc.code is None else exc.code}
        except KeyboardInterrupt:
            print("^C  execution interrompue", file=sys.stderr)
            return {"ok": False, "type": "KeyboardInterrupt", "msg": "interrompu", "line": 0}
        except BaseException as exc:
            traceback.print_exc()
            return {"ok": False, "type": type(exc).__name__,
                    "msg": str(exc), "line": self._lineno(exc, filename)}

    def interrupt(self) -> bool:
        """Leve KeyboardInterrupt dans le thread d'execution."""
        thread = self.thread
        if thread is None or not thread.is_alive() or thread.ident is None:
            return False
        # Debloque une eventuelle attente sur input().
        try:
            self.stdin.queue.put_nowait(None)
        except queue.Full:
            pass
        n = ctypes.pythonapi.PyThreadState_SetAsyncExc(
            ctypes.c_ulong(thread.ident), ctypes.py_object(KeyboardInterrupt))
        if n > 1:  # securite : on annule si plusieurs threads ont ete touches
            ctypes.pythonapi.PyThreadState_SetAsyncExc(ctypes.c_ulong(thread.ident), None)
            return False
        return n == 1


# --------------------------------------------------------------------------
# Serveur HTTP
# --------------------------------------------------------------------------

class Handler(BaseHTTPRequestHandler):
    server_version = "PyTerm/1.0"
    protocol_version = "HTTP/1.1"

    kernel: Kernel
    token: str = ""
    serve_app: bool = True

    # -- helpers -----------------------------------------------------------

    def log_message(self, fmt, *args):  # silence : la console reste lisible
        if self.server.verbose:  # type: ignore[attr-defined]
            sys.stderr.write("%s - %s\n" % (self.address_string(), fmt % args))

    def _cors(self) -> None:
        origin = self.headers.get("Origin") or "*"
        self.send_header("Access-Control-Allow-Origin", origin)
        self.send_header("Vary", "Origin")
        self.send_header("Access-Control-Allow-Headers", "Content-Type, X-PyTerm-Token")
        self.send_header("Access-Control-Allow-Methods", "GET, POST, OPTIONS")
        self.send_header("Access-Control-Max-Age", "600")

    def _json(self, payload: dict, code: int = 200) -> None:
        data = json.dumps(payload, ensure_ascii=False).encode("utf-8")
        self.send_response(code)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(data)))
        self.send_header("Cache-Control", "no-store")
        self._cors()
        self.end_headers()
        self.wfile.write(data)

    def _body(self) -> dict:
        length = int(self.headers.get("Content-Length") or 0)
        if length <= 0 or length > MAX_BODY:
            return {}
        try:
            return json.loads(self.rfile.read(length).decode("utf-8"))
        except (ValueError, UnicodeDecodeError):
            return {}

    def _authorized(self, query: dict) -> bool:
        if not self.token:
            return True
        given = self.headers.get("X-PyTerm-Token") or (query.get("token") or [""])[0]
        return given == self.token

    # -- routes ------------------------------------------------------------

    def do_OPTIONS(self):
        self.send_response(204)
        self._cors()
        self.send_header("Content-Length", "0")
        self.end_headers()

    def do_GET(self):
        parsed = urlparse(self.path)
        route, query = parsed.path, parse_qs(parsed.query)

        if route in ("/kernel", "/packages", "/events") and not self._authorized(query):
            return self._json({"error": "jeton invalide"}, 403)

        if route == "/kernel":
            return self._json({
                "status": "ok",
                "version": platform.python_version(),
                "implementation": platform.python_implementation(),
                "platform": platform.platform(),
                "executable": sys.executable,
                "cwd": str(self.kernel.workdir),
                "busy": self.kernel.busy(),
                "blockingStdin": True,
                "interrupt": True,
            })

        if route == "/packages":
            return self._json({"names": sorted({m.split(".")[0] for m in list(sys.modules)})})

        if route == "/events":
            return self._events()

        if self.serve_app:
            return self._static(route)
        self.send_error(404)

    def do_POST(self):
        parsed = urlparse(self.path)
        route, query = parsed.path, parse_qs(parsed.query)
        if not self._authorized(query):
            return self._json({"error": "jeton invalide"}, 403)

        body = self._body()

        if route == "/exec":
            code = str(body.get("code") or "")
            started = self.kernel.submit(
                code, bool(body.get("echo")),
                str(body.get("filename") or "<pyterm>"), body.get("stdin"))
            if not started:
                # L'interface attend toujours un "done" : on le lui donne.
                BUS.send({"type": "done", "ms": 0, "result": {
                    "ok": False, "type": "RuntimeError",
                    "msg": "le noyau execute deja du code", "line": 0}})
            return self._json({"ok": started, "busy": not started})

        if route == "/stdin":
            self.kernel.stdin.queue.put(body.get("data"))
            return self._json({"ok": True})

        if route == "/interrupt":
            return self._json({"ok": self.kernel.interrupt()})

        if route == "/reset":
            if self.kernel.busy():
                self.kernel.interrupt()
            self.kernel.reset()
            return self._json({"ok": True})

        if route == "/install":
            return self._install(str(body.get("name") or "").strip())

        if route == "/fs/sync":
            return self._sync(body.get("files") or {})

        self.send_error(404)

    # -- implementations ---------------------------------------------------

    def _events(self):
        q = BUS.subscribe()
        self.send_response(200)
        self.send_header("Content-Type", "text/event-stream; charset=utf-8")
        self.send_header("Cache-Control", "no-store")
        self.send_header("Connection", "keep-alive")
        self.send_header("X-Accel-Buffering", "no")
        self._cors()
        self.end_headers()
        try:
            self.wfile.write(b": connecte\n\n")
            self.wfile.flush()
            while True:
                try:
                    payload = q.get(timeout=15)
                except queue.Empty:
                    self.wfile.write(b": ping\n\n")   # garde la connexion vivante
                    self.wfile.flush()
                    continue
                self.wfile.write(b"data: " + payload.encode("utf-8") + b"\n\n")
                self.wfile.flush()
        except (BrokenPipeError, ConnectionResetError, OSError):
            pass
        finally:
            BUS.unsubscribe(q)

    def _install(self, name: str):
        if not name or any(c in name for c in ";|&`$<>\n"):
            return self._json({"ok": False, "error": "nom de paquet invalide"})
        BUS.send({"type": "stdout", "data": "pip install %s\n" % name})
        try:
            proc = subprocess.run(
                [sys.executable, "-m", "pip", "install", "--disable-pip-version-check", name],
                capture_output=True, text=True, timeout=900)
        except (subprocess.TimeoutExpired, OSError) as exc:
            return self._json({"ok": False, "error": str(exc)})
        BUS.send({"type": "stdout", "data": proc.stdout[-8000:]})
        if proc.returncode != 0:
            BUS.send({"type": "stderr", "data": proc.stderr[-8000:]})
            return self._json({"ok": False, "error": "pip a renvoye %d" % proc.returncode})
        return self._json({"ok": True})

    def _sync(self, files: dict):
        """Recopie les fichiers de l'editeur dans le dossier de travail."""
        root = self.kernel.workdir.resolve()
        written = 0
        for rel, content in files.items():
            if not isinstance(content, str):
                continue
            target = (root / rel).resolve()
            if root not in target.parents and target != root:
                continue  # jamais en dehors du dossier de travail
            target.parent.mkdir(parents=True, exist_ok=True)
            try:
                if target.exists() and target.read_text(encoding="utf-8") == content:
                    continue
            except (OSError, UnicodeDecodeError):
                pass
            target.write_text(content, encoding="utf-8")
            written += 1
        return self._json({"ok": True, "written": written})

    def _static(self, route: str):
        rel = route.lstrip("/") or "index.html"
        target = (APP_DIR / rel).resolve()
        if APP_DIR not in target.parents and target != APP_DIR:
            return self.send_error(403)
        if target.is_dir():
            target = target / "index.html"
        if not target.is_file():
            return self.send_error(404)

        types = {
            ".html": "text/html; charset=utf-8",
            ".js": "text/javascript; charset=utf-8",
            ".css": "text/css; charset=utf-8",
            ".json": "application/json; charset=utf-8",
            ".webmanifest": "application/manifest+json; charset=utf-8",
            ".svg": "image/svg+xml",
            ".png": "image/png",
            ".md": "text/markdown; charset=utf-8",
            ".py": "text/plain; charset=utf-8",
        }
        data = target.read_bytes()
        self.send_response(200)
        self.send_header("Content-Type", types.get(target.suffix, "application/octet-stream"))
        self.send_header("Content-Length", str(len(data)))
        self.send_header("Cache-Control", "no-cache")
        # Isolation du site : debloque SharedArrayBuffer, donc input() en direct
        # et l'interruption Ctrl+C du moteur Pyodide. require-corp plutot que
        # credentialless, que Safari ne connait pas : les ressources externes
        # sont chargees en mode CORS (crossorigin="anonymous").
        self.send_header("Cross-Origin-Opener-Policy", "same-origin")
        self.send_header("Cross-Origin-Embedder-Policy", "require-corp")
        self.send_header("Cross-Origin-Resource-Policy", "same-origin")
        self.end_headers()
        self.wfile.write(data)


class Server(ThreadingHTTPServer):
    daemon_threads = True
    allow_reuse_address = True
    verbose = False


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(
        description="Noyau CPython + serveur d'interface pour PyTerm.")
    parser.add_argument("--host", default="127.0.0.1",
                        help="adresse d'ecoute (defaut : 127.0.0.1)")
    parser.add_argument("--port", type=int, default=8777, help="port (defaut : 8777)")
    parser.add_argument("--workdir", default=None,
                        help="dossier de travail des scripts (defaut : ~/pyterm-workspace)")
    parser.add_argument("--token", default="",
                        help="jeton exige sur chaque requete (obligatoire hors 127.0.0.1)")
    parser.add_argument("--no-app", action="store_true",
                        help="n'exposer que l'API, sans servir l'interface")
    parser.add_argument("--verbose", action="store_true", help="journaliser les requetes")
    args = parser.parse_args(argv)

    loopback = args.host in ("127.0.0.1", "::1", "localhost")
    if not loopback and not args.token:
        parser.error("--token est obligatoire des que --host sort de 127.0.0.1 : "
                     "ce service execute le code qu'il recoit.")

    workdir = Path(args.workdir).expanduser() if args.workdir else Path.home() / "pyterm-workspace"
    workdir.mkdir(parents=True, exist_ok=True)
    os.chdir(workdir)
    if str(workdir) not in sys.path:
        sys.path.insert(0, str(workdir))

    Handler.kernel = Kernel(workdir)
    Handler.token = args.token
    Handler.serve_app = not args.no_app

    httpd = Server((args.host, args.port), Handler)
    httpd.verbose = args.verbose

    shown = args.host if args.host != "0.0.0.0" else "<adresse-de-la-machine>"
    suffix = ("?token=" + args.token) if args.token else ""
    print("PyTerm — noyau %s %s" % (platform.python_implementation(), platform.python_version()))
    print("  dossier de travail : %s" % workdir)
    if Handler.serve_app:
        print("  interface          : http://%s:%d/%s" % (shown, args.port, suffix))
    print("  API du noyau       : http://%s:%d" % (shown, args.port))
    print("  Ctrl+C pour arreter.")
    try:
        httpd.serve_forever()
    except KeyboardInterrupt:
        print("\narret.")
    finally:
        httpd.server_close()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

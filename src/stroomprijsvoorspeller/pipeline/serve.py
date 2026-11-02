"""Lokale server voor de site, met een ververs-knop die de pipeline start (besluit 49).

Serveert de map site/ en twee lokale eindpunten die op een statische host niet bestaan:
- GET  /api/local/status   -> {"bezig": bool, "laatste": {...}, "regels": [...]}
- POST /api/local/ververs  -> start `epv daily --type auto` op de achtergrond (één tegelijk)

De site werkt zonder deze eindpunten: dan toont de knop alleen de instructie om ververs.bat te starten.
"""

from __future__ import annotations

import json
import logging
import subprocess
import sys
import threading
import webbrowser
from functools import partial
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer

import pandas as pd

from stroomprijsvoorspeller.config import Config

log = logging.getLogger(__name__)

STATUS = {"bezig": False, "gestart_utc": None, "klaar_utc": None, "exit": None, "run_type": None, "regels": []}
_LOCK = threading.Lock()


def _start_run(cfg: Config, run_type: str) -> bool:
    with _LOCK:
        if STATUS["bezig"]:
            return False
        STATUS.update(bezig=True, gestart_utc=pd.Timestamp.now(tz="UTC").isoformat(), klaar_utc=None, exit=None,
                      run_type=run_type, regels=[])

    def werk():
        cmd = [sys.executable, "-m", "stroomprijsvoorspeller", "--config", str(cfg.root / "config.yaml"), "daily", "--type", run_type]
        proc = subprocess.Popen(cmd, cwd=cfg.root, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True,
                                encoding="utf-8", errors="replace")
        for regel in proc.stdout:
            with _LOCK:
                STATUS["regels"] = (STATUS["regels"] + [regel.rstrip()])[-200:]
        proc.wait()
        with _LOCK:
            STATUS.update(bezig=False, klaar_utc=pd.Timestamp.now(tz="UTC").isoformat(), exit=proc.returncode)

    threading.Thread(target=werk, daemon=True).start()
    return True


class Handler(SimpleHTTPRequestHandler):
    cfg: Config

    def end_headers(self):
        if self.path.endswith(".json") or self.path.startswith("/api/local/"):
            self.send_header("Cache-Control", "no-store")
        super().end_headers()

    def _json(self, obj: dict, status: int = 200) -> None:
        body = json.dumps(obj, ensure_ascii=False).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def do_GET(self):
        if self.path.split("?")[0] == "/api/local/status":
            with _LOCK:
                self._json({**STATUS, "regels": STATUS["regels"][-30:], "lokaal": True})
            return
        super().do_GET()

    def do_POST(self):
        pad = self.path.split("?")[0]
        if pad == "/api/local/ververs":
            lengte = int(self.headers.get("Content-Length") or 0)
            body = json.loads(self.rfile.read(lengte) or b"{}") if lengte else {}
            run_type = body.get("type", "auto")
            if run_type not in ("auto", "hoofd", "verversing"):
                self._json({"fout": "onbekend type"}, 400)
                return
            gestart = _start_run(self.cfg, run_type)
            self._json({"gestart": gestart, "bezig": True})
            return
        self._json({"fout": "onbekend pad"}, 404)

    def log_message(self, fmt, *args):
        log.debug(fmt, *args)


def serve(cfg: Config, poort: int = 8766, open_browser: bool = False) -> None:
    site = cfg.root / "site"
    handler = partial(Handler, directory=str(site))
    Handler.cfg = cfg
    server = ThreadingHTTPServer(("127.0.0.1", poort), handler)
    url = f"http://localhost:{poort}/"
    log.info("site op %s (map %s); stoppen met Ctrl+C", url, site)
    print(f"Site: {url}  (Ctrl+C om te stoppen)")
    if open_browser:
        webbrowser.open(url)
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        server.server_close()

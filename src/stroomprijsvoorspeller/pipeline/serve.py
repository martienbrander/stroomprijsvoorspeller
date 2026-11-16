"""Lokale server voor de site, met een ververs-knop die de pipeline start (besluit 49).

Serveert de map site/ en twee lokale eindpunten die op een statische host niet bestaan:
- GET  /api/local/status   -> {"bezig": bool, "laatste": {...}, "regels": [...]}
- POST /api/local/ververs  -> start `epv daily --type auto` op de achtergrond (één tegelijk)

De site werkt zonder deze eindpunten: dan toont de knop alleen de instructie om ververs.bat te starten.
"""

from __future__ import annotations

import json
import logging
import socket
import subprocess
import sys
import threading
import webbrowser
from functools import partial
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer

import pandas as pd

from stroomprijsvoorspeller.config import Config

log = logging.getLogger(__name__)

MAX_REGELS = 200   # zoveel uitvoerregels van de lopende run bewaren we
# toestand van de ververs-knop, gedeeld tussen de serverdraden; alleen lezen en schrijven binnen _LOCK
STATUS = {"bezig": False, "gestart_utc": None, "klaar_utc": None, "exit": None, "run_type": None, "regels": []}
_LOCK = threading.Lock()


def _start_run(cfg: Config, run_type: str) -> bool:
    """Start `epv daily` in een eigen proces en houdt de laatste uitvoerregels bij. False als er al een run loopt."""
    with _LOCK:
        if STATUS["bezig"]:
            return False
        STATUS.update(bezig=True, gestart_utc=pd.Timestamp.now(tz="UTC").isoformat(), klaar_utc=None, exit=None,
                      run_type=run_type, regels=[])

    def werk() -> None:
        cmd = [sys.executable, "-m", "stroomprijsvoorspeller", "--config", str(cfg.root / "config.yaml"), "daily", "--type", run_type]
        proc = subprocess.Popen(cmd, cwd=cfg.root, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True,
                                encoding="utf-8", errors="replace")
        for regel in proc.stdout:
            with _LOCK:
                STATUS["regels"] = (STATUS["regels"] + [regel.rstrip()])[-MAX_REGELS:]
        proc.wait()
        with _LOCK:
            STATUS.update(bezig=False, klaar_utc=pd.Timestamp.now(tz="UTC").isoformat(), exit=proc.returncode)

    threading.Thread(target=werk, daemon=True).start()
    return True


class Handler(SimpleHTTPRequestHandler):
    cfg: Config

    def end_headers(self) -> None:
        # lokale server: nooit cachen, anders blijft de browser na een update het oude script of de oude JSON gebruiken
        self.send_header("Cache-Control", "no-store")
        super().end_headers()

    def _json(self, obj: dict, status: int = 200) -> None:
        body = json.dumps(obj, ensure_ascii=False).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def do_GET(self) -> None:
        if self.path.split("?")[0] == "/api/local/status":
            with _LOCK:
                self._json({**STATUS, "regels": STATUS["regels"][-30:], "lokaal": True})
            return
        super().do_GET()

    def do_POST(self) -> None:
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

    def log_message(self, fmt: str, *args) -> None:
        log.debug(fmt, *args)


def netwerk_adressen() -> list[str]:
    """IPv4-adressen van deze pc op het lokale netwerk (voor de telefoon op dezelfde wifi)."""
    adressen = set()
    try:
        for info in socket.getaddrinfo(socket.gethostname(), None, socket.AF_INET):
            ip = info[4][0]
            if not ip.startswith("127."):
                adressen.add(ip)
    except OSError:
        pass
    # het adres waarmee naar buiten gepraat wordt is meestal het juiste wifi-adres; zet dat vooraan
    try:
        s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        s.connect(("192.0.2.1", 80))  # geen verkeer, alleen routekeuze
        voorkeur = s.getsockname()[0]
        s.close()
        adressen.discard(voorkeur)
        return [voorkeur, *sorted(adressen)]
    except OSError:
        return sorted(adressen)


def serve(cfg: Config, poort: int = 8766, open_browser: bool = False, netwerk: bool = False) -> None:
    """Serveert de site. Standaard alleen voor deze pc; met `netwerk=True` ook voor apparaten op hetzelfde (wifi)netwerk,
    bijvoorbeeld een telefoon (besluit 57). Windows Firewall vraagt dan eenmalig om toestemming voor Python."""
    site = cfg.root / "site"
    handler = partial(Handler, directory=str(site))
    Handler.cfg = cfg
    server = ThreadingHTTPServer(("0.0.0.0" if netwerk else "127.0.0.1", poort), handler)
    url = f"http://localhost:{poort}/"
    log.info("site op %s (map %s); stoppen met Ctrl+C", url, site)
    print(f"Site: {url}  (Ctrl+C om te stoppen)", flush=True)
    if netwerk:
        adressen = netwerk_adressen()
        if adressen:
            print("Op je telefoon of een andere pc op hetzelfde wifinetwerk: " + "  of  ".join(f"http://{a}:{poort}/" for a in adressen))
        else:
            print("Ook bereikbaar op het lokale netwerk; het adres van deze pc staat bij `ipconfig` (IPv4-adres).")
        print("Vraagt Windows Firewall om toestemming? Kies dan 'toestaan' voor privenetwerken.", flush=True)
    if open_browser:
        webbrowser.open(url)
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        server.server_close()

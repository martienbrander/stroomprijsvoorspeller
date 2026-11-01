"""Gemeenschappelijke HTTP-laag: retries, backoff, nette User-Agent."""

from __future__ import annotations

import logging
import time

import requests

log = logging.getLogger(__name__)

USER_AGENT = "stroomprijsvoorspeller/0.1 (open source; https://github.com/)"


def get_json(url: str, params: dict, *, session: requests.Session | None = None,
             retries: int = 5, timeout: int = 60) -> dict:
    """GET met JSON-antwoord. Probeert opnieuw bij 429/5xx en netwerkfouten, met oplopende wachttijd."""
    s = session or requests.Session()
    wacht = 2.0
    laatste: Exception | None = None
    for poging in range(retries):
        try:
            r = s.get(url, params=params, timeout=timeout, headers={"User-Agent": USER_AGENT})
            if r.status_code == 429 or r.status_code >= 500:
                raise requests.HTTPError(f"HTTP {r.status_code}: {r.text[:200]}", response=r)
            r.raise_for_status()
            try:
                return r.json()
            except ValueError as e:  # leeg of geen JSON (bijv. foutpagina): opnieuw proberen
                raise requests.HTTPError(f"geen JSON in antwoord: {r.text[:200]!r}", response=None) from e
        except (requests.ConnectionError, requests.Timeout, requests.HTTPError) as e:
            laatste = e
            status = getattr(getattr(e, "response", None), "status_code", None)
            if status is not None and 400 <= status < 500 and status != 429:
                raise
            log.warning("poging %d/%d mislukt voor %s: %s; wacht %.0fs", poging + 1, retries, url, e, wacht)
            time.sleep(wacht)
            wacht = min(wacht * 2, 60)
    raise RuntimeError(f"opgegeven na {retries} pogingen: {url}") from laatste

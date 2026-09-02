"""Tiny cached HTTP helper. stdlib only, polite, resumable."""

from __future__ import annotations

import gzip
import hashlib
import time
import urllib.error
import urllib.request
from pathlib import Path

USER_AGENT = "nix-arsenal-importer/0.1 (+https://github.com/OWNER/nix-arsenal)"
CACHE = Path(".cache/http")
RETRIES = 3
BACKOFF = 2.0


def get(url: str, *, cache: bool = True, timeout: int = 60) -> bytes:
    """Fetch a URL, caching to .cache/http so re-runs are cheap and offline-ish.

    Importers walk thousands of files. Without the cache you will get rate
    limited by GitHub within a minute, and you will re-download 400MB of
    PKGBUILDs every time you tweak a mapping rule.
    """
    key = hashlib.sha256(url.encode()).hexdigest()[:32]
    path = CACHE / key[:2] / key
    if cache and path.is_file():
        return gzip.decompress(path.read_bytes())

    last: Exception | None = None
    for attempt in range(RETRIES):
        try:
            req = urllib.request.Request(url, headers={"User-Agent": USER_AGENT})
            with urllib.request.urlopen(req, timeout=timeout) as resp:
                body = resp.read()
            break
        except urllib.error.HTTPError as exc:
            if exc.code in (403, 429) and attempt < RETRIES - 1:
                time.sleep(BACKOFF * (attempt + 1) * 5)
                last = exc
                continue
            raise
        except Exception as exc:  # noqa: BLE001 - network is allowed to be flaky
            last = exc
            if attempt == RETRIES - 1:
                raise
            time.sleep(BACKOFF * (attempt + 1))
    else:  # pragma: no cover
        raise RuntimeError(f"giving up on {url}: {last}")

    if cache:
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(gzip.compress(body))
    return body


def get_text(url: str, **kw) -> str:
    return get(url, **kw).decode("utf-8", errors="replace")

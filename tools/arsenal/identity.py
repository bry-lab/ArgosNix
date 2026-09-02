"""Canonical identity for a tool.

The whole catalog hinges on this module. Distro package names diverge
constantly -- crackmapexec became netexec, Kali's dirbuster is not BlackArch's
dirbuster, half of REMnux ships under names that exist nowhere else. What does
not diverge is where the code lives. So identity is the normalised upstream
URL, and every importer's job is to resolve its packages to one.

Normalisation rules, in order:
  - lowercase scheme and host, force https
  - drop credentials, port, query, fragment
  - strip a leading 'www.'
  - map known mirrors/redirects to their canonical host
  - strip a trailing '.git' and trailing slashes
  - for known forges, keep only owner/repo (drop /tree/main, /issues, /wiki)
  - lowercase the path for forges that are case-insensitive on owner/repo
    (GitHub and GitLab are, in practice, for identity purposes)

Anything that fails to parse degrades to a 'urn:name:<id>' pseudo-URL so the
entry still has a stable key and shows up in reports as needing attention.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from urllib.parse import urlsplit

# Forges where the first two path segments are the whole identity.
FORGES = {
    "github.com",
    "gitlab.com",
    "codeberg.org",
    "bitbucket.org",
    "gitee.com",
    "salsa.debian.org",
    "gitlab.gnome.org",
    "gitlab.freedesktop.org",
    "git.sr.ht",
}

# Hosts that are mirrors of, or redirect to, another host.
HOST_ALIASES = {
    "www.github.com": "github.com",
    "raw.githubusercontent.com": "github.com",
    "gist.github.com": "github.com",
    "github.io": "github.com",
    "pypi.python.org": "pypi.org",
    "www.pypi.org": "pypi.org",
    "sourceforge.net": "sourceforge.net",
    "sf.net": "sourceforge.net",
}

# Paths on these hosts that are pages *about* a project rather than the project.
FORGE_NOISE = re.compile(
    r"/(tree|blob|releases|issues|wiki|pulls|actions|tags|commits|archive|raw)(/.*)?$"
)

_SLUG_OK = re.compile(r"^[a-z0-9][a-z0-9._+-]*$")


@dataclass(frozen=True, slots=True)
class Identity:
    """A normalised upstream reference."""

    url: str
    forge: str | None = None
    owner: str | None = None
    repo: str | None = None

    @property
    def is_synthetic(self) -> bool:
        return self.url.startswith("urn:")

    def __str__(self) -> str:  # pragma: no cover - trivial
        return self.url


def normalise(raw: str | None, *, fallback: str | None = None) -> Identity:
    """Reduce an arbitrary upstream string to a comparable Identity."""
    if not raw or not raw.strip():
        return _synthetic(fallback)

    raw = raw.strip()

    # git@github.com:owner/repo.git -> https://github.com/owner/repo
    scp = re.match(r"^(?:git\+)?(?:ssh://)?git@([^:/]+)[:/](.+)$", raw)
    if scp:
        raw = f"https://{scp.group(1)}/{scp.group(2)}"

    raw = re.sub(r"^git\+", "", raw)
    if "://" not in raw:
        raw = "https://" + raw

    try:
        parts = urlsplit(raw)
    except ValueError:
        return _synthetic(fallback)

    host = (parts.hostname or "").lower()
    if not host:
        return _synthetic(fallback)
    if host.startswith("www."):
        host = host[4:]
    host = HOST_ALIASES.get(host, host)

    path = parts.path or ""

    # github.io project pages: owner.github.io/repo -> github.com/owner/repo
    gh_pages = re.match(r"^([a-z0-9-]+)\.github\.io$", host)
    if gh_pages:
        segs = [s for s in path.split("/") if s]
        if segs:
            host, path = "github.com", f"/{gh_pages.group(1)}/{segs[0]}"

    if host in FORGES:
        path = FORGE_NOISE.sub("", path)
        segs = [s for s in path.split("/") if s]
        # sourcehut owners carry a leading '~'
        if len(segs) >= 2:
            owner, repo = segs[0], segs[1]
            repo = re.sub(r"\.git$", "", repo)
            owner, repo = owner.lower(), repo.lower()
            return Identity(
                url=f"https://{host}/{owner}/{repo}",
                forge=host,
                owner=owner,
                repo=repo,
            )

    path = re.sub(r"\.git$", "", path).rstrip("/")
    url = f"https://{host}{path}"
    return Identity(url=url)


def _synthetic(fallback: str | None) -> Identity:
    slug = slugify(fallback or "unknown")
    return Identity(url=f"urn:name:{slug}")


def slugify(name: str) -> str:
    """Canonical id form: lowercase, dashes, no surprises."""
    s = name.strip().lower()
    s = re.sub(r"[\s_]+", "-", s)
    s = re.sub(r"[^a-z0-9.+-]", "", s)
    s = re.sub(r"-{2,}", "-", s).strip("-.")
    return s or "unknown"


def is_valid_id(name: str) -> bool:
    return bool(_SLUG_OK.match(name))


def shard_for(tool_id: str) -> str:
    """Which catalog/tools/<shard>.toml an id belongs in."""
    first = tool_id[:1]
    if first.isalpha():
        return first
    return "0"

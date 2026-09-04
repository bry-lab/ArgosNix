"""`argos` -- catalog maintenance CLI.

    argos validate                 schema + referential integrity
    argos import <source>          populate the catalog from an upstream source
    argos coverage --write         regenerate docs/COVERAGE.md
    argos verify --promote         resolve entries against nixpkgs
    argos profile dfir             what is in a profile, and what is missing
    argos missing --tier 2         the packaging backlog, prioritised
    argos new sometool             scaffold a catalog entry + derivation

Run from the repo root.
"""

from __future__ import annotations

import argparse
import json
import os
import sys
from pathlib import Path

from . import coverage as coverage_mod
from . import profiles as profiles_mod
from .catalog import Catalog, Tool
from .identity import normalise, slugify
from .importers import ALL as IMPORTERS
from .taxonomy import Taxonomy


def find_root(start: Path | None = None) -> Path:
    here = (start or Path.cwd()).resolve()
    for candidate in [here, *here.parents]:
        if (candidate / "catalog" / "taxonomy.toml").is_file():
            return candidate
    # Fall back to a catalog bundled at build time, so `nix run .#argos` works
    # from any directory, not only inside a checkout. A real checkout still wins
    # (the walk above), so `argos coverage --write` and friends stay writable.
    env = os.environ.get("ARGOS_ROOT")
    if env and (Path(env) / "catalog" / "taxonomy.toml").is_file():
        return Path(env)
    raise SystemExit("not inside an Argos repo (no catalog/taxonomy.toml found)")


# -- commands -------------------------------------------------------------


def cmd_validate(args, root: Path) -> int:
    taxonomy = Taxonomy.load(root)
    catalog = Catalog.load(root)
    errors = catalog.validate(taxonomy.keys)

    profiles = profiles_mod.load(root)
    for profile in profiles.values():
        for cat in profile.categories:
            if cat != "*" and cat not in taxonomy.categories:
                errors.append(f"profile {profile.name}: unknown category {cat!r}")
        for tool_id in [*profile.extra, *profile.exclude]:
            if tool_id not in catalog.tools:
                errors.append(f"profile {profile.name}: unknown tool {tool_id!r}")

    errors += _check_by_name(root, catalog)

    # Derivations with no catalog entry claiming them. A warning rather than an
    # error, because the normal workflow is to land the derivation, confirm it
    # builds, and only then set `local` -- a half-finished package should not
    # block everyone else's CI.
    warnings = _orphan_derivations(root, catalog)

    for warn in warnings:
        print(f"warning: {warn}", file=sys.stderr)

    if errors:
        for err in errors:
            print(f"error: {err}", file=sys.stderr)
        print(f"\n{len(errors)} problem(s) in {len(catalog)} entries", file=sys.stderr)
        return 1
    print(f"ok: {len(catalog)} entries, {len(taxonomy.keys)} categories, "
          f"{len(profiles)} profiles")
    return 0


def _by_name_dirs(root: Path) -> set[str]:
    by_name = root / "pkgs" / "by-name"
    if not by_name.is_dir():
        return set()
    return {
        path.name for path in by_name.iterdir()
        if path.is_dir() and (path / "package.nix").is_file()
    }


def _check_by_name(root: Path, catalog: Catalog) -> list[str]:
    """Every `local` must point at a derivation that exists."""
    present = _by_name_dirs(root)
    errors = []
    for tool in catalog:
        if tool.local and tool.local not in present:
            errors.append(
                f"{tool.id}: local = {tool.local!r} but "
                f"pkgs/by-name/{tool.local}/package.nix does not exist"
            )
    return errors


def _orphan_derivations(root: Path, catalog: Catalog) -> list[str]:
    claimed = {tool.local for tool in catalog if tool.local}
    return [
        f"pkgs/by-name/{name} is not claimed by any catalog entry "
        f"(set local = {name!r} once it builds)"
        for name in sorted(_by_name_dirs(root) - claimed)
    ]


def cmd_fmt(args, root: Path) -> int:
    catalog = Catalog.load(root)
    written = catalog.save(root)
    print(f"wrote {len(written)} shard(s), {len(catalog)} entries")
    return 0


def cmd_import(args, root: Path) -> int:
    taxonomy = Taxonomy.load(root)
    catalog = Catalog.load(root)
    module = IMPORTERS[args.source]

    kwargs = {"limit": args.limit}
    if args.source in ("blackarch", "remnux"):
        kwargs["offline"] = args.offline

    counts = {"added": 0, "merged": 0, "unchanged": 0, "skipped": 0}
    warnings: list[str] = []

    for tool, warning in module.collect(taxonomy, **kwargs):
        if warning:
            warnings.append(warning)
        if tool is None:
            counts["skipped"] += 1
            continue
        _, action = catalog.upsert(tool, source=args.source)
        counts[action] += 1

    if args.dry_run:
        print("(dry run, nothing written)")
    else:
        catalog.save(root)

    print(f"{args.source}: " + ", ".join(f"{v} {k}" for k, v in counts.items()))
    if warnings:
        log = root / ".cache" / f"import-{args.source}.log"
        log.parent.mkdir(parents=True, exist_ok=True)
        log.write_text("\n".join(warnings) + "\n", encoding="utf-8")
        print(f"{len(warnings)} warning(s) -> {log}")
        for line in warnings[:10]:
            print(f"  warn: {line}")
        if len(warnings) > 10:
            print(f"  ... and {len(warnings) - 10} more")
    return 0


def cmd_coverage(args, root: Path) -> int:
    taxonomy = Taxonomy.load(root)
    catalog = Catalog.load(root)
    report = coverage_mod.compute(catalog, taxonomy)

    if args.json:
        out = coverage_mod.to_json(report)
    else:
        out = coverage_mod.to_markdown(report, taxonomy)

    if args.write:
        target = root / "docs" / ("coverage.json" if args.json else "COVERAGE.md")
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(out, encoding="utf-8")
        print(f"wrote {target.relative_to(root)}")
    else:
        print(out, end="")
    return 0


def cmd_verify(args, root: Path) -> int:
    from . import nixpkgs  # imported lazily; needs `nix` on PATH

    catalog = Catalog.load(root)
    errors, promotions = nixpkgs.verify(catalog, promote=args.promote)

    for line in promotions:
        print(f"promote: {line}")
    for line in errors:
        print(f"error: {line}", file=sys.stderr)

    if args.promote and promotions:
        catalog.save(root)
        print(f"promoted {len(promotions)} entries to tier 1")
    return 1 if errors else 0


def cmd_profile(args, root: Path) -> int:
    catalog = Catalog.load(root)
    profiles = profiles_mod.load(root)

    if args.name is None:
        for profile in profiles.values():
            summary = profiles_mod.summarise(profile, catalog)
            print(f"{summary['name']:<10} {summary['packaged']:>5}/{summary['tools']:<5} "
                  f"({summary['percent']:>5}%)  {summary['description']}")
        return 0

    profile = profiles.get(args.name)
    if profile is None:
        raise SystemExit(f"unknown profile {args.name!r}")

    tools = profiles_mod.resolve(profile, catalog)
    for tool in tools:
        if tool.packaged:
            if not args.missing:
                print(f"  {tool.id:<28} {tool.attr}")
        elif args.missing or args.all:
            print(f"  {tool.id:<28} -- MISSING (tier {tool.tier}, "
                  f"{tool.builder or 'builder unknown'})")

    summary = profiles_mod.summarise(profile, catalog)
    print(f"\n{summary['packaged']}/{summary['tools']} available "
          f"({summary['percent']}%), {summary['missing']} missing")
    return 0


def cmd_missing(args, root: Path) -> int:
    """The packaging backlog, ordered by how many distros ship it.

    Tools that appear in three distros are worth packaging before ones that
    appear in one. This is the queue a contributor should work from.
    """
    catalog = Catalog.load(root)
    rows = [
        t for t in catalog
        if not t.packaged and (args.tier is None or t.tier == args.tier)
        and (args.category is None or args.category in t.categories)
    ]
    rows.sort(key=lambda t: (-len(t.provenance), t.tier, t.id))

    for tool in rows[: args.limit]:
        distros = ",".join(sorted(tool.provenance))
        print(f"{tool.id:<28} t{tool.tier} {(tool.builder or '?'):<10} "
              f"[{distros}] {tool.upstream}")
    print(f"\n{len(rows)} unpackaged", file=sys.stderr)
    return 0


def cmd_new(args, root: Path) -> int:
    catalog = Catalog.load(root)
    tool_id = slugify(args.name)
    if tool_id in catalog.tools:
        raise SystemExit(f"{tool_id} already exists")

    identity = normalise(args.upstream, fallback=tool_id)
    catalog.tools[tool_id] = Tool(
        id=tool_id,
        upstream=identity.url,
        categories=args.categories or ["utilities"],
        tier=2 if args.builder else 3,
        builder=args.builder,
        local=tool_id if args.builder else None,
    )
    catalog.save(root)
    print(f"added catalog entry {tool_id}")

    if args.builder:
        stub = root / "pkgs" / "by-name" / tool_id / "package.nix"
        stub.parent.mkdir(parents=True, exist_ok=True)
        if not stub.exists():
            stub.write_text(_STUB[args.builder].format(pname=tool_id, url=identity.url),
                            encoding="utf-8")
            print(f"scaffolded {stub.relative_to(root)}")
            print("next: nix-init --url", identity.url, "  # to fill in hashes")
    return 0


_STUB = {
    "go": '''{{ lib, buildGoModule, fetchFromGitHub }}:

buildGoModule rec {{
  pname = "{pname}";
  version = "0.0.0";

  src = fetchFromGitHub {{
    owner = "TODO";
    repo = "{pname}";
    rev = "v${{version}}";
    hash = lib.fakeHash;
  }};

  vendorHash = lib.fakeHash;

  meta = with lib; {{
    description = "TODO";
    homepage = "{url}";
    license = licenses.mit;
    mainProgram = "{pname}";
    platforms = platforms.unix;
  }};
}}
''',
    "rust": '''{{ lib, rustPlatform, fetchFromGitHub }}:

rustPlatform.buildRustPackage rec {{
  pname = "{pname}";
  version = "0.0.0";

  src = fetchFromGitHub {{
    owner = "TODO";
    repo = "{pname}";
    rev = "v${{version}}";
    hash = lib.fakeHash;
  }};

  cargoHash = lib.fakeHash;

  meta = with lib; {{
    description = "TODO";
    homepage = "{url}";
    license = licenses.mit;
    mainProgram = "{pname}";
    platforms = platforms.unix;
  }};
}}
''',
    "python": '''{{ lib, python3Packages, fetchFromGitHub }}:

python3Packages.buildPythonApplication rec {{
  pname = "{pname}";
  version = "0.0.0";
  pyproject = true;

  src = fetchFromGitHub {{
    owner = "TODO";
    repo = "{pname}";
    rev = "v${{version}}";
    hash = lib.fakeHash;
  }};

  build-system = with python3Packages; [ setuptools ];
  dependencies = with python3Packages; [ ];

  # Most security tools have no usable test suite, and the ones that do often
  # need network. Enable if it actually works.
  doCheck = false;

  meta = with lib; {{
    description = "TODO";
    homepage = "{url}";
    license = licenses.mit;
    mainProgram = "{pname}";
    platforms = platforms.unix;
  }};
}}
''',
    "script": '''{{ lib, stdenvNoCC, fetchFromGitHub, makeWrapper, python3 }}:

stdenvNoCC.mkDerivation rec {{
  pname = "{pname}";
  version = "0.0.0";

  src = fetchFromGitHub {{
    owner = "TODO";
    repo = "{pname}";
    rev = "v${{version}}";
    hash = lib.fakeHash;
  }};

  nativeBuildInputs = [ makeWrapper ];

  installPhase = ''
    runHook preInstall
    install -Dm755 {pname}.py $out/bin/{pname}
    wrapProgram $out/bin/{pname} \\
      --prefix PATH : ${{lib.makeBinPath [ python3 ]}}
    runHook postInstall
  '';

  meta = with lib; {{
    description = "TODO";
    homepage = "{url}";
    license = licenses.mit;
    mainProgram = "{pname}";
    platforms = platforms.unix;
  }};
}}
''',
}


# -- entrypoint -----------------------------------------------------------


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="argos", description=__doc__)
    sub = parser.add_subparsers(dest="command", required=True)

    sub.add_parser("validate", help="schema and referential integrity").set_defaults(
        func=cmd_validate
    )
    sub.add_parser("fmt", help="normalise catalog files").set_defaults(func=cmd_fmt)

    imp = sub.add_parser("import", help="populate the catalog from a distro")
    imp.add_argument("source", choices=sorted(IMPORTERS))
    imp.add_argument("--limit", type=int, default=None)
    imp.add_argument("--offline", action="store_true", help="use cached clones only")
    imp.add_argument("--dry-run", action="store_true")
    imp.set_defaults(func=cmd_import)

    cov = sub.add_parser("coverage", help="coverage report")
    cov.add_argument("--json", action="store_true")
    cov.add_argument("--write", action="store_true", help="write into docs/")
    cov.set_defaults(func=cmd_coverage)

    ver = sub.add_parser("verify", help="check catalog against nixpkgs")
    ver.add_argument("--promote", action="store_true",
                     help="rewrite entries that now exist in nixpkgs as tier 1")
    ver.set_defaults(func=cmd_verify)

    prof = sub.add_parser("profile", help="inspect a profile")
    prof.add_argument("name", nargs="?")
    prof.add_argument("--missing", action="store_true", help="only unpackaged tools")
    prof.add_argument("--all", action="store_true", help="include unpackaged tools")
    prof.set_defaults(func=cmd_profile)

    miss = sub.add_parser("missing", help="the packaging backlog")
    miss.add_argument("--tier", type=int, choices=[1, 2, 3, 4])
    miss.add_argument("--category")
    miss.add_argument("--limit", type=int, default=50)
    miss.set_defaults(func=cmd_missing)

    new = sub.add_parser("new", help="scaffold a catalog entry")
    new.add_argument("name")
    new.add_argument("--upstream", required=True)
    new.add_argument("--builder", choices=sorted(_STUB))
    new.add_argument("--categories", nargs="+")
    new.set_defaults(func=cmd_new)

    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    root = find_root()
    return args.func(args, root)


if __name__ == "__main__":
    raise SystemExit(main())

# Contributing

## The highest-value contribution

Package one tool from the backlog:

```sh
nix develop .#dev
arsenal missing --tier 2               # sorted by how many distros ship it
arsenal new sometool --upstream https://github.com/x/y --builder go
nix-init --url https://github.com/x/y  # fills in hashes
nix build .#sometool
arsenal validate
```

Then read [docs/UPSTREAMING.md](docs/UPSTREAMING.md) — if the tool is broadly
useful, send it to nixpkgs instead and we will point at it.

## Catalog changes

Edit `catalog/tools/*.toml`, then:

```sh
arsenal fmt        # normalise formatting; CI checks this
arsenal validate   # schema + referential integrity
```

Rules that are enforced:

- `upstream` is the identity. Two entries may not share one.
- Tier 1 requires a real `nixpkgs` attribute — `arsenal verify` checks it exists.
- Tier 4 must not claim a package.
- At most four categories. If you want five, the taxonomy is wrong; open an
  issue about the taxonomy instead.
- Do not hand-edit `provenance`. Importers own it.

## Adding a category

Rarely correct. It breaks profiles and forces recategorising everything nearby.
Open an issue first and make the case that the existing 20 genuinely cannot hold
the tool.

## Adding a profile

Easy and welcome, if it is a job someone actually does. A profile should be
usable standalone — no "you will also need X" in the docs. If you find yourself
listing eight `extra` tools, the taxonomy needs fixing rather than the profile.

## Tool selection

We catalogue what the four source distros ship, plus what people actually use.
We do not catalogue:

- Novel offensive capability that does not already exist publicly.
- Anything whose primary purpose is non-consensual surveillance of individuals.
- Tools we cannot legally redistribute (these get a tier-4 entry and a note, so
  the coverage number stays honest).

## Code

Python is stdlib-only and must stay that way — it runs in CI, in a build sandbox
and on contributors' laptops. `ruff check tools/` must pass. Nix is formatted
with `nixpkgs-fmt`.

Comments should explain *why*, especially where something looks odd. Several
things in this repo look odd for good reasons and there are comments saying so.

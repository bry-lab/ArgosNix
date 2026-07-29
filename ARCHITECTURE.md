# Architecture

## The one decision everything follows from

**The catalog is data. The flake is generated from it.**

The alternative — hand-written package lists in `.nix` files — works fine for a
few hundred packages and collapses entirely at three thousand. You cannot
diff it, you cannot compute coverage against Kali from it, you cannot let a
scraper maintain it, and every tool that appears in four categories appears in
four lists that immediately drift.

So: `catalog/tools/*.toml` is the source of truth. `nix/catalog.nix` reads it
with `builtins.fromTOML`. No code generation step, no checked-in generated Nix,
no import-from-derivation. One source of truth, readable by both the Python
tooling and the evaluator.

## Identity: dedupe on upstream, not name

This is the second-most-important decision and the one people get wrong.

Package names diverge across distros constantly. `crackmapexec` became
`netexec`. Kali's `dirbuster` is not BlackArch's. REMnux ships things under
names that exist nowhere else. Deduplicating on name produces a catalog with
hundreds of accidental duplicates and hundreds of accidental merges.

What does not diverge is where the code lives. So identity is the normalised
upstream URL (`tools/arsenal/identity.py`), and every importer's job is to
resolve its packages to one. `arsenal validate` fails if two entries claim the
same upstream.

The normaliser handles the cases that actually come up: `git@` URLs, `.git`
suffixes, `github.io` project pages, `/tree/main` noise, case differences in
owner/repo, and known mirrors. Entries whose upstream cannot be determined get a
`urn:name:` pseudo-URL so they still have a stable key and still show up in
reports as needing attention — they are not silently dropped.

## Tiers: making the work schedulable

| Tier | Meaning | Who does it |
| --- | --- | --- |
| 1 | Already in nixpkgs | Nobody. Free. |
| 2 | Mechanically packageable — Go with go.mod, Rust with Cargo.lock, Python with pyproject | `nix-init` + review. Batchable, hundreds per month. |
| 3 | Manual work — hostile build systems, Python 2, patched forks | A human afternoon each. |
| 4 | Will not package — unfree, binary blob, abandoned | Documented, never attempted. |

Tier 2 is where the throughput is, because most modern security tooling is Go or
Python. Tier 4 exists so the coverage number stays honest: pretending Burp Pro
is a packaging backlog item rather than a licensing wall helps nobody.

`arsenal missing` sorts the backlog by how many source distros ship a tool.
Something in three distros is worth an afternoon; something in one usually is
not.

## Importers

Four scrapers, run in descending order of metadata quality:

1. **BlackArch** — PKGBUILDs with machine-readable `url=`, `license=`, `groups=`.
   The best source by a wide margin; ~2,800 packages and their groups are
   already a usable taxonomy. Shallow clone, regex parse. We never execute a
   PKGBUILD.
2. **Kali** — one APT index gives package names, `Homepage:`, and the dependency
   sets of the `kali-tools-*` metapackages. Those metapackages are Kali's
   curated taxonomy and it is cleaner than BlackArch's, so it wins on category
   assignment where the two disagree.
3. **REMnux** — SaltStack states. Worst metadata, highest unique-tool rate:
   its malware and document-analysis coverage barely overlaps the others.
4. **Athena** — pacman repo database. Mostly re-exports BlackArch, so this
   should produce mostly merges. A high add-rate here means the BlackArch import
   failed.

The invariant that makes re-running safe: **importers may only fill blank fields
and extend provenance.** Hand curation always wins. That lives in
`Catalog.upsert` and must not be weakened.

## Taxonomy

Ours, not any distro's. BlackArch's ~50 groups are noisy and put tools in five
groups at once; Kali's ~20 metapackages are cleaner but shaped around their
menu. `catalog/taxonomy.toml` defines ~20 categories and maps upstream groups
into them, capped at three per tool.

## Profiles

Composed from categories, defined in `catalog/profiles.toml`, resolved by both
`nix/profiles.nix` and `tools/arsenal/profiles.py`.

Two implementations of the same logic is a smell. It is deliberate: contributors
on macOS without Nix still need to ask "what is in the dfir profile", and
shelling out to `nix eval` for every CLI query is unusable. Both paths run in CI.

## Capabilities

Catalog entries declare what privileges they need (`raw-socket`, `net-admin`,
`packet-capture`, `usb`, `kvm`). `modules/nixos` turns that into
`security.wrappers`, driver selection and udev rules. The devShell cannot grant
any of it and says so in its banner.

This is the piece that makes the difference between "a package set" and "a
distro replacement", and it is why the NixOS module and the ISO are first-class
outputs rather than an afterthought.

## What is deliberately not here

- **A parallel nixpkgs.** Broadly useful derivations go upstream. See
  [UPSTREAMING.md](UPSTREAMING.md).
- **Version pinning of tools.** Security tooling wants to be current; a
  six-month-old nuclei is materially worse. Pinning happens per engagement, in
  the consumer's `flake.lock`, not here.
- **A GUI.** The ISO ships Sway and a terminal. Add your own.

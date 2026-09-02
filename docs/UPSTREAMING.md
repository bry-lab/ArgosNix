# Upstreaming policy

**Default: if a tool is broadly useful, it belongs in nixpkgs, not here.**

This is the single biggest determinant of whether this project is alive in two
years. A repo that owns 2,500 derivations dies the moment its maintainer gets
bored. A repo that owns a catalog, a taxonomy, a set of profiles and a few
hundred long-tail derivations is maintainable by a handful of people
indefinitely — and every upstreamed package gets nixpkgs' CI, its maintainers,
its cache and its update bots for free.

## The rule

| Situation | Where it goes |
| --- | --- |
| Tool is used outside security work, or by many security people | nixpkgs |
| Tool is popular in ≥2 of our source distros | nixpkgs |
| Tool is niche, or a fork, or has an awkward licence | `pkgs/by-name/` here |
| Tool needs patches nixpkgs will not take | here, with a comment saying why |
| Version bump ahead of nixpkgs | `overlays/`, temporarily, with a PR link |

## Workflow

1. Package it here first. It is faster to iterate, and users get it immediately.
2. Open the nixpkgs PR. Link it in a comment in the derivation.
3. When it lands, run `arsenal verify --promote`. The entry becomes tier 1, the
   local derivation is deleted, and the catalog now points at nixpkgs.

Step 3 is automated nightly. Nothing rots.

## Carrying a version bump

Legitimate, and common: nixpkgs release cycles are slower than security tooling
release cycles. Put the override in `overlays/default.nix`, link the nixpkgs PR
in a comment, and delete it when the PR lands. An override with no linked PR
gets removed at the next audit.

## Things that stay here forever

- Anything unfree or non-redistributable (catalogued tier 4, never packaged).
- Tools whose upstream is abandoned but which are still worth having.
- Aggressive forks and patched variants that nixpkgs would reasonably reject.
- The catalog, taxonomy, profiles, modules and images. Those are the product.

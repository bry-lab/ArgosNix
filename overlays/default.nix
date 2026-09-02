# The overlay carries three things:
#   1. our own derivations from pkgs/by-name
#   2. fixes and version bumps we are carrying ahead of nixpkgs
#   3. nothing else -- resist the urge to patch unrelated packages here, it
#      forces a rebuild of everything downstream and blows out the cache
final: prev:

(import ../pkgs { inherit (prev) lib; inherit (final) callPackage; })

// {
  # Example of category 2. Security tooling moves faster than nixpkgs release
  # cycles, and a six-month-old nuclei is a materially worse nuclei because the
  # template format changes. Bumps like this belong here only until the nixpkgs
  # PR lands; leave a link.
  #
  # nuclei = prev.nuclei.overrideAttrs (old: rec {
  #   version = "3.x.y";
  #   src = final.fetchFromGitHub { ... };
  #   # upstream: https://github.com/NixOS/nixpkgs/pull/NNNNNN
  # });
}
